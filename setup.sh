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
aws lambda publish-layer-version --layer-name pandas --zip-file fileb://panda_layer.zip --compatible-runtimes python3.7

echo 'Packaging and uploading lambda code to S3'
# Upload Lambda Code
cd ..
mkdir app && cd app
wget https://raw.githubusercontent.com/herbertgoto/aws-elasticache-graviton/master/app/lambda_function.py
virtualenv elasticacheLambda
source ./elasticacheLambda/bin/activate
mv lambda_function.py elasticacheLambda/lib/python*/site-packages/
mv requirements.txt elasticacheLambda/lib/python*/site-packages/
cd elasticacheLambda/lib/python*/site-packages/
deactivate
zip -r9 elasticacheLambda.zip .
aws s3 cp elasticacheLambda.zip s3://$BUCKET_NAME