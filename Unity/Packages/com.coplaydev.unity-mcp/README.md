# MCP for Unity — エディタープラグインの操作ガイド

この文書は、同梱した MCP for Unity を Unity エディター内で設定・使用するための案内です。インストール方法は別資料に譲り、ここではエディターの画面、クライアント設定、問題の調査を扱います。引用符内の英語は実際の画面に表示されるボタン名・状態名です。

## ウィンドウを開く

- Unity のメニューから「Window > MCP for Unity」を選びます。

画面は「Server Status」「Unity Bridge」「MCP Client Configuration」「Script Validation」の 4 領域に分かれます。

## 初期設定

1. 「Window > MCP for Unity」を開きます。
2. 「Auto-Setup」を選びます。
3. 指示が表示された場合は、必要に応じて次を行います。
   - 同梱の実装を使う場合は、パッケージ内の `Server` フォルダーを選びます。
   - Python または uv/uvx がなければインストールします。
   - Claude Code を使う場合は `claude` CLI が導入されていることを確認します。
4. Unity Bridge が「Stopped」の場合は「Start Bridge」を選びます。
5. 利用する MCP クライアント（Cursor、VS Code、OpenClaw、Claude Code など）を接続します。

## サーバーの状態

- 状態を示す印とラベルには「Installed」「Installed (Embedded)」「Not Installed」があります。
- 動作モードは「Auto」または「Standard」です。Unity 側のポート番号は画面に表示され、MCP 側は 6500 です。
- 主な操作:
  - 「Auto-Setup」: 選択した MCP クライアントの登録・更新とブリッジ接続を行います。成功後は「Connected ✓」と表示されます。
  - 「Rebuild MCP Server」: Python 製 MCP サーバーを再構築します。
  - 「Select server folder…」: ローカルの `Server` フォルダーを選びます。主に開発用で、通常 uvx を使う場合は不要です。
  - 「Verify again」: サーバーの有無を再確認します。
  - Python が検出されない場合は「Open Install Instructions」を使います。
- 「HTTP Server Command」を展開すると、Unity が実行する `uvx` コマンドを確認できます。コマンドのコピーや「Start Local HTTP Server」の実行もできます。

## Unity Bridge

ブリッジの状態は「Running」または「Stopped」として表示されます。「Start/Stop Bridge」で、MCP クライアントと Unity の間で通信するブリッジを切り替えます。「Auto-Setup」の後、Auto モードでは自動的に起動する場合があります。

## MCP クライアントの設定

「Select Client」で接続先のクライアントを選びます。

- Cursor / VS Code / Windsurf:
  - 「Auto Configure」: 現在のパッケージ版を `uvx` で起動する設定を書き込みます。コマンドは `uvx`（または指定したパス）、引数は `--from <git-url> mcp-for-unity` です。
  - 「Manual Setup」: クライアント設定に貼り付ける JSON の例を開きます。
  - 「Choose UV Install Location」: uv/uvx が PATH にない場合、その実行ファイルを指定します。
  - uv とサーバーの検出後、「Config:」に設定ファイル名が表示されます。
- Claude Code:
  - 「Register with Claude Code」「Unregister MCP for Unity with Claude Code」で登録を切り替えます。
  - CLI が見つからない場合は「Choose Claude Install Location」で指定します。検出された CLI のパスは画面に表示されます。
- OpenClaw:
  - `~/.openclaw/openclaw.json` と `openclaw-mcp-bridge` プラグインを使用します。
  - MCP for Unity は `plugins.entries.openclaw-mcp-bridge.config.servers.unityMCP` に設定を書き込みます。
  - 通信方式は MCP for Unity で選んだ `HTTP` または `stdio` に従います。
  - ブリッジからは `unityMCP__call` などのプロキシツールを利用できます。

画面には状態を示す印と、「Configured」「uv Not Found」「Claude Not Found」などの短い状態名が表示されます。自動設定には「Auto Configure」、設定内容を確認しながらコピーする場合には「Manual Setup」を使います。

## スクリプトの検証

「Validation Level」では、用途に応じて次の段階を選びます。説明は選択欄の下に表示されます。

- 「Basic」: 構文のみ
- 「Standard」: 構文と Unity の慣例
- 「Comprehensive」: 全項目と意味解析
- 「Strict」: 詳細な意味検証。Roslyn が必要です。

## 問題の調査

- Python または `uv` が見つからない場合: [Cursor、VS Code、Windsurf 向けの設定ガイド](https://github.com/CoplayDev/unity-mcp/wiki/1.-Fix-Unity-MCP-and-Cursor,-VSCode-&-Windsurf)
- Claude CLI が見つからない場合: [Claude Code 向けの設定ガイド](https://github.com/CoplayDev/unity-mcp/wiki/2.-Fix-Unity-MCP-and-Claude-Code)

## 補足

- macOS では Cmd+Shift+M、Windows と Linux では Ctrl+Shift+M で MCP for Unity のウィンドウを切り替えられます。
- 問題を調べるときは、画面上部の「Show Debug Logs」を有効にすると Console に詳細が表示されます。
