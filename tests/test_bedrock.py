import boto3
import json

client = boto3.client(
    "bedrock-runtime",
    region_name="ap-southeast-1"
)

response = client.invoke_model(
    modelId="amazon.nova-lite-v1:0",
    body=json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {"text": "Hi"}
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 10
        }
    })
)

print(json.loads(response["body"].read()))