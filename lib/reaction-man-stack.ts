import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';

export interface ReactionManStackProps extends cdk.StackProps {
  slackBotTokenParameterName: string;
  slackSigningSecretParameterName: string;
}

export class ReactionManStack extends cdk.Stack {
  public readonly functionUrl: lambda.FunctionUrl;

  constructor(scope: Construct, id: string, props: ReactionManStackProps) {
    super(scope, id, props);

    if (!props.slackBotTokenParameterName || !props.slackSigningSecretParameterName) {
      throw new Error('Slack parameter names must be provided.');
    }

    const handler = new lambda.Function(this, 'ReactionManHandler', {
      runtime: lambda.Runtime.PYTHON_3_14,
      architecture: lambda.Architecture.ARM_64,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'handler.lambda_handler',
      description: 'Processes Slack Events API calls and adds emoji reactions.',
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
      environment: {
        SLACK_BOT_TOKEN_PARAMETER: props.slackBotTokenParameterName,
        SLACK_SIGNING_SECRET_PARAMETER: props.slackSigningSecretParameterName,
        SLACK_REACTIONS: 'thumbsup,tada,rocket',
      },
    });

    handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['ssm:GetParameter'],
        resources: [
          this.formatArn({
            service: 'ssm',
            resource: 'parameter',
            resourceName: props.slackBotTokenParameterName.replace(/^\//, ''),
          }),
          this.formatArn({
            service: 'ssm',
            resource: 'parameter',
            resourceName: props.slackSigningSecretParameterName.replace(/^\//, ''),
          }),
        ],
      }),
    );

    this.functionUrl = handler.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ['*'],
        allowedMethods: [lambda.HttpMethod.POST],
        allowedHeaders: ['*'],
      },
    });

    new cdk.CfnOutput(this, 'FunctionUrl', {
      value: this.functionUrl.url,
    });
  }
}
