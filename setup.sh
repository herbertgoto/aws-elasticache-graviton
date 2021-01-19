#!/bin/bash

echo 'Create and publish Lambda Layer for Pandas'
# Create Lambda Layer for Pandas
mkdir folder
cd folder
virtualenv v-env
source ./v-env/bin/activate
pip install pandas
deactivate

mkdir python
cd python
cp -r ../v-env/lib64/python*/site-packages/* .
cd ..
zip -r panda_layer.zip python
aws lambda publish-layer-version --layer-name pandas --zip-file fileb://panda_layer.zip --compatible-runtimes python3.7 python3.8

echo 'Packaging and uploading lambda code to S3'
# Upload Lambda Code
cd ..
mkdir app && cd app
wget https://raw.githubusercontent.com/aws-samples/amazon-documentdb-samples/master/samples/change-streams/app/lambda_function.py
touch requirements.txt
echo 'boto3==1.16.55' > requirements.txt
python -m venv elasticacheLambda
source elasticacheLambda/bin/activate
mv lambda_function.py elasticacheLambda/lib/python*/site-packages/
mv requirements.txt elasticacheLambda/lib/python*/site-packages/
cd elasticacheLambda/lib/python*/site-packages/
pip install -r requirements.txt 
deactivate
mv ../dist-packages/* .
zip -r9 elasticacheLambda.zip .
aws s3 cp elasticacheLambda.zip s3://$BUCKET_NAME