# 数据库备份节点 Zip 下载接口

本文说明数据库备份库模块里“按节点下载 zip 备份文件”的接口，用于浏览器下载、运维排查和自动化脚本调用。

## 适用场景

- 已知数据库备份节点 ID，需要直接下载对应 zip 文件
- 需要先探测文件是否存在、大小是多少、校验值是否变化
- 需要从外部脚本拉取某个备份节点的数据库快照

## 接口概览

### 下载 zip

`GET /api/database-backups/nodes/{node_id}/zip`

说明：

- 返回节点关联的 zip 二进制流
- 响应头会带上文件名、长度、校验值等元信息
- 浏览器在已登录状态下可直接访问该地址下载

### 探测 zip 元信息

`HEAD /api/database-backups/nodes/{node_id}/zip`

说明：

- 不返回文件内容，只返回响应头
- 适合脚本先判断文件是否存在、大小是否变化，再决定是否下载

## 鉴权要求

这个接口支持两种鉴权方式，满足任意一种即可：

- Web 登录态 Cookie
- `Authorization: Bearer <token>`

### 方式一：Web 登录态 Cookie

- 先调用 `POST /api/auth/login`
- 登录成功后，服务端会写入名为 `toolbox_session` 的 Cookie
- 后续访问下载接口时，携带这个 Cookie

### 方式二：Bearer Token

- 在服务端配置环境变量 `TOOLBOX_DOWNLOAD_API_KEY`
- 调用接口时加请求头：

```text
Authorization: Bearer <TOOLBOX_DOWNLOAD_API_KEY>
```

适用场景：

- 外部脚本下载
- CI / 自动化任务下载
- 不方便维持浏览器登录态的场景

如果既没有有效 Cookie，也没有有效 Bearer Token，接口会返回 `401 Unauthorized`。

## 路径参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `node_id` | `string` | 是 | 数据库备份节点 ID，例如 `f7fe83ac-fcc8-41b3-855a-23076b40e601` |

## 成功响应

### `GET /zip`

状态码：

- `200 OK`

响应体：

- 文件二进制流

常见响应头：

| 响应头 | 说明 |
| --- | --- |
| `Content-Type` | 文件 MIME 类型，当前通常为 `application/zip` |
| `Content-Length` | 文件大小，单位字节 |
| `Content-Disposition` | 下载文件名，浏览器通常据此保存 |
| `ETag` | 当前文件的 sha256 值包装后的标识 |
| `Last-Modified` | 文件最后修改时间 |
| `X-File-Sha256` | 文件 sha256，便于自动化校验 |

### `HEAD /zip`

状态码：

- `200 OK`

响应体：

- 空

响应头：

- 与 `GET /zip` 基本一致

## 常见错误响应

### `401 Unauthorized`

说明：

- 未携带 `toolbox_session`
- 登录态已过期
- Cookie 对应的用户已失效
- Bearer Token 缺失或错误

可能返回的 `detail`：

- `未登录。`
- `登录已过期。`
- `用户不存在。`
- `下载 API Key 无效。`

### `404 Not Found`

说明：

- 节点不存在
- 节点存在，但底层 zip 文件记录不存在
- 文件记录存在，但磁盘上的 zip 文件已丢失

可能返回的 `detail`：

- `备份节点不存在。`
- `备份 zip 文件不存在。`

## 调用示例

### 浏览器直接下载

前提：

- 你已经在 Web 页面登录过 Odoo Toolbox

直接打开：

```text
http://<host>:8001/api/database-backups/nodes/<node_id>/zip
```

例如：

```text
http://81.70.95.163:8001/api/database-backups/nodes/f7fe83ac-fcc8-41b3-855a-23076b40e601/zip
```

如果当前浏览器里有有效登录态，浏览器会直接开始下载；如果没有登录态，会返回 `401`。

### curl 用登录态下载

```bash
BASE_URL="http://81.70.95.163:8001"
NODE_ID="f7fe83ac-fcc8-41b3-855a-23076b40e601"

curl -c cookie.txt \
  -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"你的密码"}'

curl -L -b cookie.txt \
  -o "${NODE_ID}.zip" \
  "$BASE_URL/api/database-backups/nodes/$NODE_ID/zip"
```

### curl 用 Bearer Token 下载

```bash
BASE_URL="http://81.70.95.163:8001"
NODE_ID="f7fe83ac-fcc8-41b3-855a-23076b40e601"
DOWNLOAD_TOKEN="你的 TOOLBOX_DOWNLOAD_API_KEY"

curl -L \
  -H "Authorization: Bearer $DOWNLOAD_TOKEN" \
  -o "${NODE_ID}.zip" \
  "$BASE_URL/api/database-backups/nodes/$NODE_ID/zip"
```

### curl 只看头信息

```bash
BASE_URL="http://81.70.95.163:8001"
NODE_ID="f7fe83ac-fcc8-41b3-855a-23076b40e601"

curl -I -b cookie.txt \
  "$BASE_URL/api/database-backups/nodes/$NODE_ID/zip"
```

### curl 用 Bearer Token 只看头信息

```bash
BASE_URL="http://81.70.95.163:8001"
NODE_ID="f7fe83ac-fcc8-41b3-855a-23076b40e601"
DOWNLOAD_TOKEN="你的 TOOLBOX_DOWNLOAD_API_KEY"

curl -I \
  -H "Authorization: Bearer $DOWNLOAD_TOKEN" \
  "$BASE_URL/api/database-backups/nodes/$NODE_ID/zip"
```

## 推荐调用顺序

如果你是外部脚本，建议按这个顺序调用：

1. 准备鉴权方式：登录 Cookie 或 Bearer Token
2. 调 `HEAD /api/database-backups/nodes/{node_id}/zip` 检查是否存在
3. 读取 `Content-Length`、`ETag`、`X-File-Sha256`
4. 如需下载，再调 `GET /api/database-backups/nodes/{node_id}/zip`

## 排查建议

### 浏览器里点击下载没反应

优先检查：

- 当前页面是否已登录
- 浏览器控制台里请求是否返回 `401`
- 节点详情页里的下载按钮指向的 `node_id` 是否正确

### 脚本拿到 `401`

说明脚本没有带上有效 Cookie，也没有带上有效 Bearer Token。  
可以任选一种方式：

- 先调用登录接口，并在后续请求里带上 `toolbox_session`
- 或者直接配置 `TOOLBOX_DOWNLOAD_API_KEY`，并带 `Authorization: Bearer <token>`

### 脚本拿到 `404`

需要区分两种情况：

- 节点 ID 本身不存在
- 节点存在，但关联 zip 已丢失

这两种情况都会返回 `404`，但 `detail` 不同。
