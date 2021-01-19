#!/bin/env python

import boto3
import os
import json
import pandas as pd
import logging
import datetime

"""
Identifies ElastiCache clusters that can be easily migrated to Graviton.  

Required environment variables:
GRAVITON_REDIS_SUPPORTED_VERSION: The minimal Redis version that is supported with Graviton
GRAVITON_MEMCACHED_SUPPORTED_VERSION: The minimal Memcached version that is supported with Graviton
BUCKET_NAME: The name of the bucket that will be used to stored the report. 
BUCKET_PATH: The path of the bucket that will be used to stored the report. 
SNS_TOPIC_ARN_ALERT: The topic to send exceptions.   
SNS_TOPIC: The topic to send an alert that ElastiCache Graviton candidates have been found.   

"""

elasticache_client = None               # ElastiCache client
s3_client = None                        # S3 client      
sns_client = boto3.client('sns')        # SNS client
                                  
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def load_data_s3():
    """Load data into S3."""
    
    global s3_client

    if s3_client is None:
        logger.debug('Creating new S3 client.')
        s3_client = boto3.client('s3')  

    try:
        logger.debug('Loading file to S3.')
        s3_client.upload_file('/tmp/elasticache-graviton.csv', os.environ['BUCKET_NAME'], str(os.environ['BUCKET_PATH']) 
            + '/elasticache-graviton.csv')
        s3_client.upload_file('/tmp/elasticache-ri-summary.csv', os.environ['BUCKET_NAME'], str(os.environ['BUCKET_PATH']) 
            + '/elasticache-ri-summary.csv')

    except Exception as ex:
        logger.error('Exception in loading data to s3 message: {}'.format(ex))
        send_sns_message(str(ex),'ElasticCache Graviton Finder Exception',os.environ['SNS_TOPIC_ARN_ALERT'])
        raise

def send_sns_message(message,subject,topic):
    """send an SNS alert"""
    try:
        logger.debug('Sending SNS alert.')
        response = sns_client.publish(
            TopicArn=topic,
            Message=message,
            Subject=subject,
            MessageStructure='default'
        )
    except Exception as ex:
        logger.error('Exception in publishing alert to SNS: {}'.format(ex))
        send_sns_message(str(ex), 'ElasticCache Graviton Finder Exception')
        raise


def lambda_handler(event, context):
    """Gets data from ElastiCache clusters to create a report about which instances are candidate for Graviton."""

    try:
        
        nodes = getClusterCandidates()
        getReserveNodes(nodes)
        load_data_s3()

    except Exception as ex:
        logger.error('Exception in executing analysis: {}'.format(ex))
        send_sns_message(str(ex),'ElasticCache Graviton Finder Exception',os.environ['SNS_TOPIC_ARN_ALERT'])
        raise

    else:

        return {
            'statusCode': 200,
            'body': json.dumps('Success!')
        }


def getClusterCandidates():
    """Gets data from ElastiCache clusters to create a report about which instances are candidate for Graviton."""
    
    global elasticache_client

    clusterId = []
    engine = []
    version = []
    candidate = []
    instanceTypes = []
    nodeCount = {}

    noficationFlag = 0

    if elasticache_client is None:
        logger.debug('Creating new ElastiCache client.')
        elasticache_client = boto3.client('elasticache')
    
    try:
        response = elasticache_client.describe_cache_clusters()

        while True:
            for i in response['CacheClusters']:
                if ("large" in i['CacheNodeType'] and "6g." not in i['CacheNodeType']):
                
                    clusterId.append(i['CacheClusterId'])
                    engine.append(i['Engine'])
                    version.append(i['EngineVersion'])
                    instanceTypes.append(i['CacheNodeType'])
                
                    if i['CacheNodeType'] in nodeCount:
                        nodeCount[i['CacheNodeType']]['used'] = nodeCount[i['CacheNodeType']]['used'] + 1
                    else:
                        nodeCount.update({i['CacheNodeType']: {"used": 1, "reserved": 0}})

                    if ((i['Engine'] == 'redis' and i['EngineVersion'] >= os.environ['GRAVITON_REDIS_SUPPORTED_VERSION']) or 
                        (i['Engine'] == 'memcached' and i['EngineVersion'] >= os.environ['GRAVITON_MEMCACHED_SUPPORTED_VERSION'])):
                        candidate.append('yes')
                        if noficationFlag == 0:
                            send_sns_message(
                                'ElastiCache nodes candidates for Graviton have been found. See report in S3 bucket: ' 
                                + os.environ['BUCKET_NAME'] + '/' + os.environ['BUCKET_PATH'],
                                'ElastiCache Graviton Candidates Found',
                                os.environ['SNS_TOPIC']
                            )
                            noficationFlag = 1
                else: 
                    candidate.append('no')

            if "Marker" in response:
                response = elasticache_client.describe_cache_clusters(Marker=response['Marker']) 
                continue
            else:
                break
    
        candidates={'Cluster Id': clusterId, 'Engine': engine, 'Version': version, 'Graviton': candidate, 'Node Type': instanceTypes}
        df = pd.DataFrame(candidates) 
        df.to_csv('/tmp/elasticache-graviton.csv')

    except Exception as ex:
        logger.error('Exception in analyzing clusters: {}'.format(ex))
        send_sns_message(str(ex),'ElasticCache Graviton Finder Exception',os.environ['SNS_TOPIC_ARN_ALERT'])
        raise

    return nodeCount

def getReserveNodes(nodeCount):
    
    noficationFlag = 0
    # Get cache reserve nodes
    response = elasticache_client.describe_reserved_cache_nodes()

    try:

        while True:
            for i in response['ReservedCacheNodes']:
                if ("large" in i['CacheNodeType'] and "6g." not in i['CacheNodeType'] and "active" in i['State']):
                
                    if i['CacheNodeType'] in nodeCount:
                        nodeCount[i['CacheNodeType']]['reserved'] = nodeCount[i['CacheNodeType']]['reserved'] + i['CacheNodeCount']
                    else:
                        nodeCount.update({i['CacheNodeType']: {"reserved": i['CacheNodeCount']}})
                
            if "Marker" in response:
                response = elasticache_client.describe_reserved_cache_nodes(Marker=response['Marker']) 
                continue
            else:
                break
    
        nodeType = []
        nodesReserved = []
        nodesDeployed = []
        diff = []

        for i in nodeCount:
            nodeType.append(i)
            nodesReserved.append(nodeCount[i]['reserved'])
            nodesDeployed.append(nodeCount[i]['used'])
            diff.append(nodeCount[i]['used'] - nodeCount[i]['reserved'])
            if ((nodeCount[i]['used'] - nodeCount[i]['reserved'] > 0) and noficationFlag == 0):
                send_sns_message(
                    'ElastiCache reserve node candidates have been found. See report in S3 bucket: ' 
                    + os.environ['BUCKET_NAME'] + '/' + os.environ['BUCKET_PATH'],
                    'ElastiCache Reservation Candidates Found',
                    os.environ['SNS_TOPIC']
                )
                noficationFlag = 1

        reserveSummary={'Node Type': nodeType, 'Reservations': nodesReserved,
            'Nodes deployed': nodesDeployed, 'Diff': diff}
        df = pd.DataFrame(reserveSummary) 
        df.to_csv('/tmp/elasticache-ri-summary.csv')
    
    except Exception as ex:
        logger.error('Exception in analyzing reserve nodes: {}'.format(ex))
        send_sns_message(str(ex),'ElasticCache Graviton Finder Exception',os.environ['SNS_TOPIC_ARN_ALERT'])
        raise