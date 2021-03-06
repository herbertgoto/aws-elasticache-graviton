# A solution to discover AWS ElastiCache nodes candidates for Graviton and potential reserve nodes

This solution frequently review AWS ElastiCache deployments in a region to identify potential Graviton candidate and reservations. This can be used to reduce costs and improve performance on ElastiCache workloads.  

When the solution is executed, it generates 2 csv reports in S3:

- elasticache-graviton: inventory of ElastiCache nodes and whether it is a candidate for Graviton or not (based on node type and redis/memcached version). 
- elasticache-ri-summary: inventory of ElastiCache active reservations and usage. 

If potential Graviton or reservations are found, an event is sent to an SNS topic which the user can subscribe to.

This solution is composed of:
- One Amazon EventBridge rule in charge of triggering a Lambda on a scheduled basis. By default, it is set to 8 days. 
- One SNS topic used to publish exceptions when running the Lambda. 
- One SNS topic used to publish events when potential Graviton or reservation candidates are found. 
- One Lambda function which reviews AWS ElastiCache workloads. 
- One IAM role used by Lambda to invoke SNS, S3, and ElastiCache.

This solution currently only evaluates large instance types which for now are the only ones that can be match to Graviton types offering. 

# How to install

1. Deploy a AWS Cloud9 environment and clone this repo `git clone https://github.com/herbertgoto/aws-elasticache-graviton.git`
2. Execute `export BUCKET_NAME=[Bucket Name]` where [Bucket Name] is the bucket that will host the lambda code. Make sure bucket is in the same region as the whole solution.
3. Execute `chmod 700 aws-elasticache-graviton/setup.sh` and execute `aws-elasticache-graviton/setup.sh`. This setup bash will:
    1. Create and publish a Lambda layer for Pandas
    2. Package and upload Lambda code to S3
4. Deploy the CloudFormation Stack by running the following command (it is set to be run every 8 days, you can change it):
```
aws cloudformation deploy --stack-name elasticsearch-graviton --template-file aws-elasticache-graviton/elasticache-graviton-finder.yml --parameter-overrides ParamS3Bucket=$BUCKET_NAME LambdaLayerArn=$(jq -r .'LayerVersionArn' folder/lambdaLayer-output.json) Frequency='rate(8 days)' --capabilities CAPABILITY_NAMED_IAM
```  

## Environment variables

- GRAVITON_REDIS_SUPPORTED_VERSION: The minimal Redis version that is supported with Graviton. It is set by default to 5.0.6
- GRAVITON_MEMCACHED_SUPPORTED_VERSION: The minimal Memcached version that is supported with Graviton. It is set by default to 1.5.16
- BUCKET_NAME: The name of the bucket that will be used to stored the report. 
- BUCKET_PATH: The path of the bucket that will be used to stored the report. 