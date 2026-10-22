# TicketPro 商品页面

商品页已增加订单、支付宝支付与激活码交付模块，接线及本地演示见 [支付与发货说明](docs/payment-delivery.md)。正式启用需要服务端支付配置，以及经过原授权系统验证的网站专用库存。

沿用现有商品站 `https://ticket-pro-website.vercel.app`。服务端部署文件在 `deploy/`；`python -m server.cli check` 可只读检查上线条件，`backup` 保存订单及交付配置，`reconcile` 补发漏通知订单。代码与部署包准备完成不代表已部署或真实支付验收通过。

Melon Fleet 代理中心独立教程位于 `/help/melonfleet/proxy`，内容与脚本维护说明见 [代理中心教程页](docs/melon-proxy-guide.md)。

React + Vite 商品目录。演示视频取自 `/Users/xuqihan/Desktop/插件宣传/`，每个视频商品选用该目录中按文件修改时间排序的最新视频。韩版 YES24 按用户要求与国际版共用视频，并在详情页标注视频展示的是国际版。AllTicket 展示最新演示视频和原始界面截图。寬宏 KHAM 和金光票务 Cotai Ticketing 暂时隐藏，价格留待填写。视频来源及时间记录在 [docs/video-sources.json](docs/video-sources.json)。网页播放的是已转成 H.264/AAC MP4 的文件，位于 `public/videos/<商品 ID>/latest.mp4`；封面为同目录下的 `poster.jpg`。

## 本地预览

```bash
npm install
npm run dev
```

提交前检查：

```bash
npm run lint
npm run build
```

## 商品价格

价格在 `src/data/products.js` 与 `src/data/newProducts.js` 的 `pricing` 数组中维护。每个档位使用 `{ label, duration, price }`；`price` 是人民币数值。半个月档位使用 `duration: '15天'`。韩版 YES24 是独立商品，使用与国际版相同的三档价格和独立激活码。
