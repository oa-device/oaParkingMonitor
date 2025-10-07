# Welcome to your CDK JavaScript project

This is a blank project for CDK development with JavaScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app. The build step is not required when using JavaScript.

## Multiple profiles

If you have multiple profiles defined in your `~/.aws/config` like:

```
[profile parking001]
region=ca-central-1
output=json
aws_access_key_id=<access key>
aws_secret_access_key=<secret key>
```

Make sure you set your AWS profile to diff or deploy:

```bash
export AWS_PROFILE=parking001
```

To list your profiles:

```
aws configure list-profiles
```

## Useful commands

- `npm run test` perform the jest unit tests
- `npx cdk deploy --all` deploy this all stacks to your default AWS account/region
- `npx cdk diff` compare deployed stack with current state
- `npx cdk synth` emits the synthesized CloudFormation template
