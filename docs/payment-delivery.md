# 商品页、支付和授权系统接线

网站负责订单和交付，ZPAY 负责收款，原项目服务继续负责激活、设备绑定和到期检查。原授权数据库和已有客户的激活方式保持不变。

领取页按商品显示激活码，下方只提供飞书“安装与使用教程”入口。`server/tutorials.local.json` 保存从现有管理台读取并核对的商品链接，服务端使用，不打包进前端，也不进入 Git。可用 `TICKETPRO_TUTORIALS` 指定其他路径；导入库存时优先使用显式 `--tutorial`，其次使用该映射，最后读取原项目设置。尚未核对的项目不借用其他项目教程。

## 已实现

- 商品售价和期限由 `npm run catalog` 从商品数据导出，构建前自动更新。客户端只能选择商品和期限，不能指定金额。
- 下单用数据库事务保留一枚对应商品、期限的码，无库存不能创建订单。订单、库存、交付内容持久化，订单号、交易号和激活码均有唯一约束。
- ZPAY 密钥仅存在服务端。回调要通过签名、商户、订单号、金额、方式检查，并主动向 ZPAY 查询已付款状态及交易号，再提交发货事务。重复回调、刷新页面均返回同一码。
- 订单使用独立的 256 位领取密钥。查询接口使用 Authorization 头；领取链接用 fragment 传递密钥，不进入普通请求日志或 Referer。单凭订单编号不能查看激活码。
- 浏览器按商品和期限分别保存下单重试凭据；网络响应丢失后复用原请求和领取密钥。并行订单或迟到响应只清理自身凭据，旧版待处理记录在重试时自动迁移。
- 付款页提供二维码、私密领取链接、主动查付款；订单页每 5 秒读取交付结果。成功后显示激活码、安装与使用教程和绑定说明。本机订单列表支持找回。
- 默认在订单页领取；邮件或微信自动投递尚未实现。演示模式只允许本机访问，演示和生产数据库不能混用。

## 本地演示

```sh
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
npm install
npm run catalog
TICKETPRO_DEMO=1 TICKETPRO_DB=server/data/demo.sqlite3 TICKETPRO_SITE_URL=http://127.0.0.1:5173 .venv/bin/python -m server.cli demo-seed
TICKETPRO_DEMO=1 TICKETPRO_DB=server/data/demo.sqlite3 TICKETPRO_SITE_URL=http://127.0.0.1:5173 .venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 18110 --no-access-log
npm run dev -- --host 127.0.0.1
```

点击立即购买、选择期限、创建订单、打开本地模拟付款，再点击模拟成功。不会扣款，DEMO 激活码及 example.com 资源链接不可用于正式商品。

## 与统一管理台配合

不能直接把原来的“未激活”码导入网站：它可能已经人工售出。只使用新建的网站专用批次。

1. 在原项目管理台生成新的一批绑机码，备注为 `ticketpro-web:批次名`，导出至服务器受限目录。不要从旧管理台人工发放这批码。
2. `server/product-projects.json` 已完成全部 20 个商品的对应关系。例如商品 `interpark-kr` 对应授权项目 `itp`，韩版 YES24 对应独立项目 `yes24_kr`。按用户确认，NOL Fleet 和 Melon Fleet 均销售专业版，分别对应 `nol_fleet_professional`、`melon_fleet_professional`，两者的原授权版本标识均为 `ultra`；基础版或个人版的码会被拒绝导入。没有正式库存的商品不会开放扣款。`server/license-projects.json` 是不含密钥的授权接口注册表，专门适配 Galaxy/HKTicketing/Fantopia/Klook 的 lookup 接口及 AllTicket 的管理接口。HKTicketing、Galaxy 和两款 Fleet 使用管理台登录会话，避免混淆登录密码与 API token；Fleet 的 device 绑定模式和 batch_name 字段会按原服务语义校验，并严格隔离所选版本。凭据通过其引用的服务端环境变量加载。
3. 安装统一管理台的可选过滤器：

   ```sh
   python3 scripts/connect-unified-console.py /opt/unified-license-console
   ```

   安装前自动备份 app.py，不修改项目凭据或授权数据库。设置 `UNIFIED_RESERVED_CODES_FILE` 后才启用；未设置时保持原行为。
4. 给订单服务和统一管理台配置同一个隔离清单路径，例如 `/opt/ticketpro-shared/web-reserved-codes.json`。首次可创建内容为 `{"version":1,"projects":{}}` 的空文件，再启用两侧配置。统一管理台需有读权限，订单服务需有目录写权限。文件仅含码哈希。配置后缺失或损坏时，人工取码暂停，避免误发。
5. 导入对应商品的专用库存：

   ```sh
   .venv/bin/python -m server.cli import-stock \
     --product interpark --project interpark --days 30 \
     --batch ticketpro-web:interpark-month-001 \
     --file /root/private/interpark-web-month.txt \
     --registry /opt/unified-license-console/projects.json \
     --manifest /opt/ticketpro-shared/web-reserved-codes.json \
     --tutorial https://你的正式教程地址
   ```

   导入通过原项目接口逐枚验证码值、项目、期限、批次备注、绑机方式、未激活和未吊销状态；不合格整批拒绝，重复库存拒绝导入。Ticket Plus 使用原系统的 batch 字段校验；AllTicket 的批次只接受大写等字符，应使用如 `TICKETPRO_WEB_ALLTICKET_20261020` 的格式，并通过独立管理台核对真实批次。AllTicket 的统一查询接口缺少批次信息，不能用它跳过批次验证。先原子写隔离清单，再提交可售库存。统一管理台会跳过网站批次，包含已售出但尚未激活的码。独立旧管理台仍能显示这些码，运营时不能再人工发这批。

服务器需加载注册表引用的凭据环境变量。凭据、库存和数据库不得进入 Vite 环境变量、前端 public、用户安装包或 Git。

## 部署

现有正式商品站为 `https://ticket-pro-website.vercel.app`，沿用此地址。`vercel.json` 已给生产构建设置公开的订单 API 地址 `https://api.nexuschat.top/ticketpro`；支付密钥不进入 Vercel。

2026-10-20 已将前端发布到现有 Vercel 项目，并将订单服务、Nginx 入口、每分钟补发与每日备份部署到现有 API 主机。正式接口健康检查、CORS、无签名回调拒绝和数据库备份已验证。统一管理台已启用网站库存隔离。

同日以订单 `2026102019352006983611088898` 完成 0.01 元真实支付宝付款。Zpay 管理台显示“已付款 已通知”，主动查单验证了商户、订单、金额及交易号；订单自动发出一枚独立生成的 Interpark 30 天绑机码，并显示对应飞书教程。重放两次该笔已付款交易的有效签名通知均返回 `200 success`，主动刷新和重新读取订单仍为原码，数据库分配数量始终为一枚。浏览器重新加载后仍可领取。原插件在买家电脑上的实际激活尚待验证。这次付款验收覆盖该测试商品的真实付款、通知、发货和重复请求链路。

随后按用户要求，为全部 20 个商品、64 个期限档位各补充 5 枚新生成的真实绑机码，共 320 枚。NOL Fleet、Melon Fleet 均为专业版。全部码经原授权服务逐枚核对项目、期限、专用批次、未激活、未绑定、未过期和未吊销状态后，统一导入可售库存；没有挪用旧的未激活库存。网站批次使用 `ticketpro-web:stock-20261020-...`，AllTicket 和 Ticket Plus 使用 `TICKETPRO_WEB_20261020_D...`。公开目录已核对每档库存为 5、全部售价与原目录一致；已付款测试订单及其原码保持不变。隔离清单包含全部 321 枚库存记录（320 枚可售、1 枚已售测试码），正式环境完整检查通过。

本次补库存前已对 20 个原授权数据库保存一致性快照；受限目录 `/root/ticketpro-stock-20261020` 留存生成结果、校验记录与源库备份。新码生成后先加入人工发码隔离清单，全部校验通过后才一次性提交网站库存。原控制台将空设备显示为 `-` 的兼容处理仅应用于两个脱敏设备字段；实际设备标识仍拒绝入库，并有回归测试覆盖。初次入库时 64 项后端测试通过，补库存后另执行一次订单与库存备份。后续按下节启用了自动补货。

生成服务端部署包：

```sh
.venv/bin/python scripts/package-backend.py
```

`output/ticketpro-backend.tar.gz` 只包含服务端源码、锁定依赖、教程与项目对应配置、部署文件；不包含支付密钥、激活码库存、订单数据库或前端视频。包内有私有教程配置，文件权限为 600，只传到自己的后端主机。

在后端主机解压后运行 `sudo bash deploy/install.sh`。安装器准备 `/opt/ticketpro`、独立服务账户、共享库存隔离目录、systemd 单元，并保留已有环境文件和数据库。它不会自动启动收款。填写 `/etc/ticketpro.env` 的支付和授权凭据；不要把 `.env.example` 当作已配置凭据。

将 `deploy/nginx-ticketpro.conf` 包含进 `api.nexuschat.top` 已有的 HTTPS server 块，执行 `nginx -t` 后 reload。安装统一管理台过滤器，并把 `deploy/unified-website-stock.conf` 作为它的 systemd drop-in；确认管理台服务能读取 `/opt/ticketpro-shared/web-reserved-codes.json`，重启该服务后才导入网站库存。

订单服务、补发与备份单元分别为 `ticketpro.service`、`ticketpro-reconcile.timer`、`ticketpro-backup.timer`。准备正式专用库存并完成下面检查后，启动服务和两个 timer。订单服务仅监听本机 18110；补发每分钟运行一次，每次最多 200 笔，下一轮继续剩余订单；备份每天运行，结果放在 `/var/backups/ticketpro`。备份需要另行复制到用户自己的备份位置。

参照 `.env.example`，为订单服务配置正式站点、API origin、ZPAY PID/KEY/CID、管理员密钥、正式数据库、允许的 CORS origin 和隔离清单。只监听本机 18110，通过 Nginx 提供 HTTPS。

例如 `TICKETPRO_API_URL=https://api.nexuschat.top/ticketpro`，Nginx 对 `/ticketpro/` 使用 `proxy_pass http://127.0.0.1:18110/;`，并设置 `X-Real-IP $remote_addr`。只有信任本机 Nginx 时才启用 `TICKETPRO_TRUST_LOOPBACK_PROXY=1`。

回调地址自动追加 `/commerce/zpay/notify`，返回地址追加 `/commerce/zpay/return`，不带预置查询参数。前端构建设置 `VITE_COMMERCE_API=https://api.nexuschat.top/ticketpro`，让 API 请求直接发到该域名，不经过 Vercel 的 SPA 改写。正式服务必须使用 HTTPS。

先补充 ZPAY 手续费余额，再以专用测试商品验证：真实付款成功、notify 返回 success、领取一次分配的码、刷新仍为原码、原插件能识别此码。ZPAY mapi 的返回页参数没有完整写在其公开文档中，需在上线联调中确认；订单页独立保留并通过后台通知发货，不依赖付款页跳转。

定期运行 `.venv/bin/python -m server.cli reconcile`，主动核对漏回调订单并补发。`summary` 可查看订单和库存状态（不打印明文码）。禁用或脱敏服务访问日志，避免回调查询参数进入日志。生产依赖用验证过的 lock 文件安装。

## 自动补货

2026-10-20 已按用户要求启用：`ticketpro-restock.path` 在成功发货提交后唤起独立的 `ticketpro-restock.service`，`ticketpro-restock.timer` 每 30 秒兜底核对。每个商品、期限的备货目标是 5 枚，待付款预留也计入备货；例如 4 枚可售加 1 枚待付款时不生成新码，待该订单成功发出后补 1 枚。预留期间可售数可以暂时少于 5，避免未付款订单不断触发生码。缺货期间仍禁止超卖，已有订单的发货不等待补货接口。

任务保存在订单库的 `restock_jobs` 表中，每个档位最多有一个未完成任务，批次名绑定任务编号。重复支付通知、重复唤起、进程重启均复用原任务和批次。生成前先持久化任务；旧 OCR 系统使用预先持久化的随机码，只创建原系统尚未找到的码，避免超时重试覆盖已使用记录。其余系统从原授权数据库按专用批次只读找回生成结果。结果不明时先核对该批次，不盲目生成第二批；空批次仍无法确认结果时暂停该档位的生成并保留 `review` 任务供人工核对。明确的连接失败、拒绝或校验接口暂不可用按退避时间重试。

新码进入可售库存前仍逐枚执行项目、期限、专业版、单设备、未使用及教程校验，且先发布人工发码隔离清单。隔离清单写入会保留已经隔离但尚未入库的码。库存入库与任务完成在同一个事务中提交；若运营在补货期间手动补足库存，多出的已验证新码保存为 `restock_spare`，以后优先转为可售，不超过备货目标。

发行配置 `/etc/ticketpro-stock-sources.json`、发行凭据 `/etc/ticketpro-stock.env` 均为 root 所有、600 权限，不进入 Git、前端或普通订单进程。独立任务以受限的 root systemd 单元运行，用于访问现有四个项目的官方批量管理工具及读取恢复信息；写订单库和隔离清单时切换到 `ticketpro` 身份。四个管理工具仅允许写各自现有数据目录，其余项目沿用现有授权接口，不修改原授权服务源码。

在当前 API 主机安装时可用以下配置器；不加 `--write` 只核对现有 Nginx、运行进程和数据库结构，不生成任何码，也不输出凭据：

```sh
/opt/ticketpro/.venv/bin/python /opt/ticketpro/scripts/configure-stock-sources.py --write
systemctl daemon-reload
systemctl restart ticketpro.service
systemctl enable --now ticketpro-restock.path ticketpro-restock.timer
systemctl start ticketpro-restock.service
```

加载两个服务环境文件后，`.venv/bin/python -m server.restock --check` 只报告配置和备货缺口，不生成激活码。`summary` 的 `restock` 字段和 `journalctl -u ticketpro-restock.service` 可查看任务状态、重试时间与脱敏原因。`review` 任务须先核对原批次与发行端结果，不能直接删除任务或重发生成请求。凭据轮换后在发行主机重新运行配置器，让后续任务读取新凭据。

本次本机和生产 Python 环境均通过 88 项测试。使用与正式补货任务相同的 systemd 限制，在隔离订单库中真实验证了 Interpark 永久码、Ticketmaster 月卡和 NOL Fleet 专业版年卡：各补回 1 枚、恢复到 5，重复发货和再次运行均不多生成。未创建或修改真实付款，这 3 枚新码已保留为网站备用库存。验收后公网 64 个档位仍各有 5 枚可售，324 条库存记录包含 320 枚可售、3 枚备用与 1 枚已售测试码；原订单及其激活码保留，并再次备份。

## 商家订单看板

网站的 `/admin/orders` 为独立商家页面，展示买家付款统计、14 天趋势、商品排行和分页订单列表，支持商品、订单状态、创建日期、订单号/商品名称筛选。点击订单可查看付款与飞书通知状态、已交付码和对应教程。列表与初始详情不返回激活码；仅在授权用户主动显示时，详情接口返回该已发货订单的码。待付款订单不能读取预留码，任何接口均不返回买家领取密钥哈希、客户端标识或原支付请求。

`TICKETPRO_DASHBOARD_KEY` 是独立的商家访问凭据，允许查询 `/commerce/api/admin/dashboard`、`/commerce/api/admin/orders/{id}` 及保存该订单的到账核对记录，不允许访问原管理汇总接口。原 `TICKETPRO_ADMIN_KEY` 也可以查看看板。密钥通过 Authorization 头发送；页面只在当前标签页的 sessionStorage 中保留，经私密入口 fragment 进入后会清除地址栏 fragment，不写入前端代码或 Git。

订单表新增 `is_test` 标记，默认值为 0，统计与列表默认排除测试单；只有明确标注的原 0.01 元联调订单被单独标记。不会按金额大小或商品名称自动将正常销售误判为测试。页面每 30 秒同步，创建日期筛选和收款日统计使用响应中的时区（默认 Europe/Berlin）。买家付款金额为订单实付金额，未扣除支付平台手续费，也不是商家支付宝实际到账金额。

2026-10-22 已在生产部署查询接口并核对原订单和库存记录保持一致；默认两笔正式订单实付合计 132 元，原联调单单独显示。121 项后端测试、8 项下单回归测试、前端 lint 与构建通过；浏览器已验证真实数据、测试单切换、订单搜索和默认隐藏码的详情。专用入口及访问凭据仅保存在服务器私密配置和本机 `output/订单看板私密入口.txt`，请妥善保管。

## 支付宝到账核对

2026-10-22 核对了 Zpay 的公开开发文档及两笔实际已付款订单的查询响应：返回付款状态、金额、交易号等字段，没有支付宝结算/到账状态。不会把 `status=1`、订单发货、Zpay 手续费余额或时间经过解释为已到账；不同通道存在 D+1 与 D0，未确认当前通道前不生成预计到账日。

看板新增“到账待核对 / 已确认到账 / 已核对未到账”，未付款显示“尚未付款”。已付款订单初始均待核对，不会因日期变化自动升级。商家查看支付宝账单后，可在订单详情手动保存结论，可选填写实际到账金额、账单到账日和备注，来源明确为商家核对；未填实际金额时保持空值，不用订单总额冒充扣费后的到账金额。

核对记录保存在独立的 `settlement_checks` 表，每次修改同时追加 `settlement_history`，并校验版本号，防止旧页面覆盖新记录。只有商家授权可操作，未付款订单拒绝确认到账；该操作不修改订单金额、买家支付状态、激活码、自动发货、补货或飞书通知。界面可再次核对并保留最近十次历史，数据库备份保留完整历史。135 项后端测试覆盖默认未知、授权、金额与日期、撤销、更正留痕、并发冲突及原订单不变。

参考：[Zpay 开发文档](https://api.z-pay.cn/doc.html)、[支付宝 V1/V2 通道说明](https://api.z-pay.cn/news?id=23)。

## 飞书商家订单提醒

成功发货时，在同一数据库事务中写入一条 `order_notifications` 事件。每个订单只产生一条事件，未付款订单和已有历史订单不补发提醒。消息包含商品、期限、实付金额、订单号、确认时间和自动发货结果，不含激活码、买家领取密钥或支付凭据。

独立的 `ticketpro-notify.service` 调用飞书群自定义机器人的 HTTPS Webhook；`ticketpro-notify.path` 监听成功发货信号，`ticketpro-notify.timer` 每 30 秒兜底。接口失败会退避重试，不影响买家发货和补货。工作进程用文件锁和数据库领取租约防止并行处理同一事件，发送成功须同时检查 HTTP 响应及飞书的 `code=0`。Webhook 不提供端到端幂等键；若飞书已收消息但回复丢失，或进程在发送后落库前退出，重试可能产生同订单号的重复提醒，不会重复发码。

在 `/etc/ticketpro-notify.env` 配置 `TICKETPRO_FEISHU_WEBHOOK`；机器人开启签名校验时同时配置 `TICKETPRO_FEISHU_SECRET`。可用 `TICKETPRO_NOTIFICATION_TIMEZONE` 设置消息时区，当前默认 `Europe/Berlin`。环境文件 root 所有、权限 600，仅由通知服务加载，不进入前端或 Git。主服务的 `/etc/ticketpro.env` 设置 `TICKETPRO_NOTIFICATION_SIGNAL=/var/lib/ticketpro/notify.request`，信号文件属 `ticketpro:ticketpro-web`、权限 600。

部署后，加载通知服务的两个环境文件，可运行 `python -m server.notifications --check` 检查配置和队列，`--test` 发送明确标注的接入测试消息（不创建订单、不消费库存、不改通知队列），然后启用 `ticketpro-notify.path` 和 `ticketpro-notify.timer`。`summary` 的 `notifications` 字段报告状态、次数、下次重试时间及脱敏原因；日志不输出 Webhook、签名密钥或原始上游异常。群机器人如启用关键词，关键词须包含消息中的 `TicketPro` 或 `订单通知`；IP 白名单须允许通知主机出口地址。

协议依据：[飞书自定义机器人使用指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)。

2026-10-22 已部署并启用通知服务、path 和 timer；用户提供的机器人已成功确认接收明确标注的接入测试。发货信号唤起任务、通知进程退出状态、公网正式检查及已有已售码保留均通过验证，没有补推历史已完成订单。本机及生产 Python 环境均通过 109 项后端测试，新增测试覆盖通知与发货事务一致性、重复发货、并发领取、崩溃租约恢复、失败重试、敏感信息脱敏、飞书业务错误、URL 限制与可选签名校验。

## 正式环境检查与备份

下列命令要在服务端、加载正式服务的环境变量后执行：

```sh
.venv/bin/python -m server.cli check --product interpark
.venv/bin/python -m server.cli check --product interpark --online
.venv/bin/python -m server.cli backup --directory /var/backups/ticketpro
```

`check` 只读检查配置、生产数据库模式、每个商品的项目/教程/凭据、可售库存、数据库完整性，以及全部库存是否进入人工发码隔离清单。缺项返回非零退出码，不创建数据库，不显示密钥或激活码。`--product` 可重复指定；省略时检查全部商品。`--config-only` 仅用于准备环境，不代表可正式售卖。`--online` 另验证公网正式接口和回调路由，不创建订单或发生扣款。

`backup` 用 SQLite 的一致性备份接口保存订单、库存与补货任务，同时保存教程、目录、项目对应关系及覆盖该数据库全部库存的隔离清单。备份目录 700、文件 600，成功后写入 `complete.json`；不完整备份会被移除。恢复前先停止订单、人工发码服务，以及 `ticketpro-restock.path`、`ticketpro-restock.timer`、`ticketpro-restock.service`，保留当前数据库和隔离清单的副本；恢复数据库时隔离清单须合并保留后续已售码，不能简单用旧清单覆盖，否则可能再次人工发出这些码。恢复后重新执行 `check` 再开放。

代码检查通过后仍须用真实支付完成最后验收：公网订单付款、Zpay 回调返回 success、领取的码属于所购项目与期限、原插件成功激活、重复回调/刷新不发第二枚码、关闭后重开领取链接仍可查看。只有这些通过后，才算该商品已完成上线验收。

## 待付款占用与回滚

当前不自动退款、取消交易或释放待付款库存。ZPAY 公开文档没有关闭交易接口，旧付款码可能仍可支付，所以不能仅凭超时把原码重新出售。待付款占用需经运营核对；不要直接改库释放。同一来源每小时最多创建 5 笔订单；重试同一下单请求复用原订单和库存。

部署前备份原管理台源码、配置及订单数据库。回滚不能删除发货记录，不能把已售出未激活的码重新放回人工库存；仍须保留隔离清单。移除 ZPAY KEY 可停止新下单，但须保留受限备份供既有订单核对与恢复使用。

## 验证

```sh
npm run lint
npm run build
node --test tests/commerce.test.mjs
.venv/bin/python -m pytest server/tests -q
```
