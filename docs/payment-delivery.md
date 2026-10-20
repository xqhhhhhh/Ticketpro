# 商品页、支付和授权系统接线

网站负责订单和交付，ZPAY 负责收款，原项目服务继续负责激活、设备绑定和到期检查。原授权数据库和已有客户的激活方式保持不变。

领取页按商品显示激活码，下方只提供飞书“安装与使用教程”入口。`server/tutorials.local.json` 保存从现有管理台读取并核对的商品链接，服务端使用，不打包进前端，也不进入 Git。可用 `TICKETPRO_TUTORIALS` 指定其他路径；导入库存时优先使用显式 `--tutorial`，其次使用该映射，最后读取原项目设置。尚未核对的项目不借用其他项目教程。

## 已实现

- 商品售价和期限由 `npm run catalog` 从商品数据导出，构建前自动更新。客户端只能选择商品和期限，不能指定金额。
- 下单用数据库事务保留一枚对应商品、期限的码，无库存不能创建订单。订单、库存、交付内容持久化，订单号、交易号和激活码均有唯一约束。
- ZPAY 密钥仅存在服务端。回调要通过签名、商户、订单号、金额、方式检查，并主动向 ZPAY 查询已付款状态及交易号，再提交发货事务。重复回调、刷新页面均返回同一码。
- 订单使用独立的 256 位领取密钥。查询接口使用 Authorization 头；领取链接用 fragment 传递密钥，不进入普通请求日志或 Referer。单凭订单编号不能查看激活码。
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

同日以订单 `2026102019352006983611088898` 完成 0.01 元真实支付宝付款。Zpay 管理台显示“已付款 已通知”，主动查单验证了商户、订单、金额及交易号；订单自动发出一枚独立生成的 Interpark 30 天绑机码，并显示对应飞书教程。重放两次该笔已付款交易的有效签名通知均返回 `200 success`，主动刷新和重新读取订单仍为原码，数据库分配数量始终为一枚。浏览器重新加载后仍可领取。62 项后端测试通过。正常商品价格未修改，正常可售库存尚未导入；原插件在买家电脑上的实际激活尚待验证。这次验收仅证明该测试商品的真实付款、通知、发货和重复请求链路。

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

## 正式环境检查与备份

下列命令要在服务端、加载正式服务的环境变量后执行：

```sh
.venv/bin/python -m server.cli check --product interpark
.venv/bin/python -m server.cli check --product interpark --online
.venv/bin/python -m server.cli backup --directory /var/backups/ticketpro
```

`check` 只读检查配置、生产数据库模式、每个商品的项目/教程/凭据、可售库存、数据库完整性，以及全部库存是否进入人工发码隔离清单。缺项返回非零退出码，不创建数据库，不显示密钥或激活码。`--product` 可重复指定；省略时检查全部商品。`--config-only` 仅用于准备环境，不代表可正式售卖。`--online` 另验证公网正式接口和回调路由，不创建订单或发生扣款。

`backup` 用 SQLite 的一致性备份接口保存订单与库存，同时保存教程、目录、项目对应关系及覆盖该数据库全部库存的隔离清单。备份目录 700、文件 600，成功后写入 `complete.json`；不完整备份会被移除。恢复前先停止订单和人工发码服务，保留当前数据库和隔离清单的副本；恢复数据库时隔离清单须合并保留后续已售码，不能简单用旧清单覆盖，否则可能再次人工发出这些码。恢复后重新执行 `check` 再开放。

代码检查通过后仍须用真实支付完成最后验收：公网订单付款、Zpay 回调返回 success、领取的码属于所购项目与期限、原插件成功激活、重复回调/刷新不发第二枚码、关闭后重开领取链接仍可查看。只有这些通过后，才算该商品已完成上线验收。

## 待付款占用与回滚

当前不自动退款、取消交易或释放待付款库存。ZPAY 公开文档没有关闭交易接口，旧付款码可能仍可支付，所以不能仅凭超时把原码重新出售。待付款占用需经运营核对；不要直接改库释放。同一来源每小时最多创建 5 笔订单；重试同一下单请求复用原订单和库存。

部署前备份原管理台源码、配置及订单数据库。回滚不能删除发货记录，不能把已售出未激活的码重新放回人工库存；仍须保留隔离清单。移除 ZPAY KEY 可停止新下单，但须保留受限备份供既有订单核对与恢复使用。

## 验证

```sh
npm run lint
npm run build
.venv/bin/python -m pytest server/tests -q
```
