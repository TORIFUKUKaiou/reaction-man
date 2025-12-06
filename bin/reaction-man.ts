#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ReactionManStack, ReactionManStackProps } from '../lib/reaction-man-stack';

const app = new cdk.App();

const props: ReactionManStackProps = {
  slackBotTokenParameterName:
    (app.node.tryGetContext('slackBotTokenParameterName') as string) ?? '/reaction-man/slack/bot-token',
  slackSigningSecretParameterName:
    (app.node.tryGetContext('slackSigningSecretParameterName') as string) ?? '/reaction-man/slack/signing-secret',
  slackReactions: app.node.tryGetContext('slackReactions') as string | undefined,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
};

new ReactionManStack(app, 'ReactionManStack', props);
