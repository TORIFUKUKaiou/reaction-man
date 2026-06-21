# Reaction Man

Slack メッセージに自動リアクションを付与するための AWS サーバーレス構成です。CDK(TypeScript) でインフラを定義し、Lambda (Python 3.14) と Lambda Function URL を使って Slack Events API からの HTTPS リクエストを処理します。機密情報は Systems Manager Parameter Store (SecureString) に保管します。

## アーキテクチャ

- **AWS CDK (TypeScript)**: `ReactionManStack` が Lambda、Function URL、IAM ポリシーを定義
- **AWS Lambda (Python 3.14)**: `lambda/handler.py` が Slack 署名検証、イベントハンドリング、`reactions.add` 呼び出しを担当
- **Lambda Function URL**: Slack Events API からの HTTPS エンドポイント。API Gateway は使用しません
- **AWS Systems Manager Parameter Store**: Bot Token と Signing Secret を SecureString で管理し、Lambda は実行時に復号して利用

## 前提条件

- Node.js 24 / npm
- AWS CLI と `~/.aws` にデフォルトプロファイル
- CDK v2 (`npm install -g aws-cdk`) インストール済み
- Slack アプリ (Events API を有効化、`chat:write`, `reactions:write`, `app_mentions:read`, `channels:history` などの権限)

## セットアップ

1. 依存関係をインストール

   **CloudShellで実施する場合**
   ```sh
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
   source ~/.bashrc
   nvm install 24
   nvm use 24
   npm install -g aws-cdk
   cd ~
   git clone https://github.com/TORIFUKUKaiou/reaction-man.git
   cd reaction-man
   ```

   ```sh
   npm install
   ```

2. Slack クレデンシャルを Parameter Store に登録 (例)

   ```sh
   aws ssm put-parameter \
     --name /reaction-man/slack/bot-token \
     --type SecureString \
     --value "xoxb-..." \
     --overwrite

   aws ssm put-parameter \
     --name /reaction-man/slack/signing-secret \
     --type SecureString \
     --value "xxxx" \
     --overwrite
   ```

3. (必要に応じて) `cdk.json` の context か `cdk deploy` 時の `-c` 引数でパラメータ名やリアクション絵文字を上書きできます。

   ```sh
   cdk deploy \
     -c slackBotTokenParameterName=/reaction-man/slack/bot-token \
     -c slackSigningSecretParameterName=/reaction-man/slack/signing-secret \
     -c slackReactions=heart,fire,100
   ```

4. デプロイ

   ```sh
   npm run build
   npx cdk synth
   npx cdk deploy
   ```

   デプロイ完了時に Function URL が出力されます。

5. Slack 側の設定

   - Event Subscriptions を有効化し、Request URL に Function URL を設定
   - `message.channels` など必要なイベントを購読
   - OAuth & Permissions に `reactions:write` / `channels:history` などを追加し、Bot Token を再発行
   - Signing Secret を Parameter Store に保存したものと一致させる

## Lambda 実装のポイント

- Slack 署名 (`X-Slack-Signature`, `X-Slack-Request-Timestamp`) を検証し、5 分以上前のリクエストは破棄
- `url_verification` リクエストには Challenge をそのまま返却
- `event_callback` のメッセージイベントのみ処理し、Bot 投稿やサブタイプ付きメッセージは除外
- `SLACK_REACTIONS` 環境変数でリアクション候補 (カンマ区切り) を変更可能
- Parameter Store の値は Lambda 内でキャッシュし、複数イベントでも効率的に再利用
- ログ保持期間は 1 日に設定

## ローカルテスト

Function URL を直接呼び出すユースケースのため、ローカルでの完全な再現は難しいですが、署名検証をスキップした単体テストを追加する場合は `lambda/handler.py` の関数を直接 import できます。

## 今後の拡張案

1. CloudWatch Logs Insights やメトリクス (Emoji 追加数) を可視化
2. EventBridge Scheduler 等と組み合わせた定期メッセージ対応
3. Slack モーダルや slash command から Function URL を呼び出す機能追加
