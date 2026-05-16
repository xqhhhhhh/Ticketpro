export const products = [
  {
    id: 'interpark',
    name: '国际版 Interpark 捡漏抢票工具',
    shortName: '国际版 Interpark',
    description: '支持24小时不间断捡漏、多重验证码自动突破，以及钉钉/Telegram多端消息提醒，公售会员购通杀。',
    longDescription: '专为国际版 Interpark 打造的全自动捡漏抢票神器，无论是公售、预售还是会员购均可完美支持。不仅提供比人工快得多的24小时自动锁票功能，还自带多维度定制面板，支持实时热更配置（选区、位置、刷新频率等）。内置强大的防阻断机制，全自动秒解图文及滑块验证码。抢到票后更支持浏览器、钉钉和Telegram联动通知，让你睡着也能安心拿票。',
    pricing: [
      { label: '月付', duration: '1个月', price: 80 },
      { label: '年付', duration: '1年', price: 128 },
      { label: '买断', duration: '永久', price: 168 },
    ],
    currency: '¥',
    features: ['24h 自动捡漏', '多端消息提醒', '全自动过滑块/验证码', '一机一码安全防盗'],
    badge: null,
    color: '#6366f1',
    logo: 'https://www.google.com/s2/favicons?domain=ticket.interpark.com&sz=128',
    // 本地宣传视频
    videos: [
      '/videos/interpark/promo1.mp4',
      '/videos/interpark/promo2.mp4'
    ],
    // 图文介绍
    highlights: [
      {
        title: '24小时不间断的自动化捡漏',
        description: '完全解放双手，锁票速度远超手动。不仅适用于各种新旧版活动界面（覆盖所有 ITP 演出、音乐会及 LCK 比赛等），且支持对切区频率、特定选区和位置进行精细化的参数定义，还可实时修改无需重启。',
        image: null,
      },
      {
        title: '多重验证码无缝秒解',
        description: '自动应对票务网站的反爬阻杀，无需人工守候，自动输入包含老版英文字母验证码及最新型的滑块验证码在内的多重安全验证，扫平结账前的一切障碍。',
        image: null,
      },
      {
        title: '多端及时通知与完善服务',
        description: '锁票付款成功时，可通过电脑浏览器、钉钉、Telegram 发送及时消息提醒（即使睡觉也能抢票）。采用一机一码注册制，搭配极其详尽的手把手安装教程与包永久更新的售后保障，真正做到买得放心用得舒心。',
        image: null,
      },
      {
        title: '纯净模拟点击绝对防封',
        description: '彻底摒弃修改底层协议与发包拦截等高危手法，完全基于前台浏览器的真实用户物理点击模拟。机制绝对绿色安全，不落入官方异常操作黑名单，绝无封号风险。',
        image: null,
      },
    ],
    // 真实用户反馈视频
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'melon',
    name: 'Melon 抢票捡漏插件',
    shortName: 'Melon',
    description: '硬核独立开发，独家高级全自动捡漏神器。支持跨进程多开、无限循环验证、精确到行的毫秒级秒切。',
    longDescription: '这不仅仅是一套普通的脚本。从底层框架从零手搓的绝版全自动抢票神器，一人一码防止滥用，保障超高稀缺性并承诺绝对绿色防封号。实现真正的全流程解放双手：从自动接管极验验证、拦截异常报错弹窗，到底层级别的多维选区与防冲突无缝衔接。无论你抢的是国际版还是韩版，演唱会还是音乐剧，这套硬核代码都能成为你上岸的最强后盾。',
    pricing: [
      { label: '月付', duration: '1个月', price: 80 },
      { label: '年付', duration: '1年', price: 128 },
      { label: '买断', duration: '永久', price: 168 },
    ],
    currency: '¥',
    features: ['无限循环防验证过滑块', '超精密行/列定位', '免死循环报错阻断', '同账户多端独立多开'],
    badge: null,
    color: '#10b981',
    logo: 'https://www.google.com/s2/favicons?domain=ticket.melon.com&sz=128',
    videos: [
      '/videos/melon/promo1.mp4'
    ],
    highlights: [
      {
        title: '硬核级防冲突与报错拦截',
        description: '自动拦截烦人的 please try again 弹窗。遇到座次冲突引发 “Another customer is in payment” 报错时，不会致死卡顿，而是瞬间确认并继续锁座！可灵活配置页面停留上限，彻底摆脱韩文异端弹窗封锁。',
        image: null,
      },
      {
        title: '超越底层的坐标级选座',
        description: '告别市面上粗糙落后的板块选择！独家深度支持自定义“行”、“列”甚至具体座位的超高阶选座系统！配置表可在进入界面后免重启实时热更调整，助你像手术刀一般精准插入空档。',
        image: null,
      },
      {
        title: '系统级多进程并发覆盖',
        description: '打破单兵破阵的极限！支持在同一台电脑上开启多个浏览器同时运行抢票逻辑，无论是多个账号齐开，还是使用同一账号进行高强度饱和式冲锋，通通完美兼容，大幅度暴力拉长中标率。',
        image: null,
      },
      {
        title: '全天候多端锁座联报',
        description: '让机器人替你枯燥值守！无论昼夜，成功锁座瞬间立刻通过电脑声音、手机钉钉以及无视区域封锁的 Telegram 多重发送锁座通知。躺平睡觉，睁眼出票，更有原作者直接提供一对一包更新特保。',
        image: null,
      },
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'yes24',
    name: '国际版 YES24 捡漏抢票插件',
    shortName: '国际版 YES24',
    description: '资深独立开发，巧妙降低 Code 报错风险，24小时自动化捡漏直至锁票。',
    longDescription: '这是一套独立原创开发的 YES24 全自动化捡漏脚本。针对 YES24 特有的严格风控流程进行了巧妙设计，大幅降低运行时出现系统 code 报错的风险。脚本支持全天候 24 小时无人值守式捡漏，真正做到全自动运行直到锁票为止。纯净原创代码架构，包后续的持续更新与一对一维护升级。',
    pricing: [
      { label: '月付', duration: '1个月', price: 80 },
      { label: '年付', duration: '1年', price: 128 },
      { label: '买断', duration: '永久', price: 168 },
    ],
    currency: '¥',
    features: ['防止 Code 报错', '极限量身自定义', '全天候捡漏机制', '跨平台锁座通知'],
    badge: null,
    color: '#f59e0b',
    logo: 'https://www.google.com/s2/favicons?domain=ticket.yes24.com&sz=128',
    videos: [
      '/videos/yes24/promo1.mp4'
    ],
    highlights: [
      {
        title: '智能降错流控核心',
        description: '不同于粗暴连点，脚本经过极其巧妙的安全逻辑设计，可有效应对官方页面刷新负荷，大幅度规避被识别出异常导致无限报错（Code 报错等）的风险。',
        image: null,
      },
      {
        title: '全自动持久战捡漏',
        description: '告别一直盯屏幕的煎熬。插件支持进入全天候 24h 自动化巡航模式，一旦有放弃支付或退回的遗漏余票，瞬间捕获并长驱直入直到锁票成功。',
        image: null,
      },
      {
        title: '精细化定向猎补',
        description: '不要盲目随缘，只抢你最想要的！支持深度自发配置：不仅可以提前设定心仪防线区域，还可以直接将目标收缩瞄准具体的理想位置，让代码帮你拔得头筹。',
        image: null,
      },
      {
        title: '全维度锁座级提醒',
        description: '成功锁定余票之后，不仅会在浏览器直接发出系统声音提醒，更会同步发送手机钉钉、Telegram 多重跨端锁座通知。即使睡着了，闹钟一响也能直接起床付款！',
        image: null,
      },
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'interpark-kr',
    name: '韩版 Interpark 抢票捡漏插件',
    shortName: '韩版 ITP',
    description: '完美避开国际版白屏风控，无死角支持韩版全资源。24小时全自动监控捡漏，防封绝不手软。',
    longDescription: '近期由于国际版 ITP 遭受严格风控导致频繁白屏报错，海量聪明的真实用户已全面转向韩版战场！本作专为韩版生态从零打造，涵盖演唱会、音乐会及LCK所有新老网页。无需死守屏幕，脚本支持全天候 24 小时高频刷新捡漏。不仅能在遭遇滑块、字母验证码时自动秒解，还自带彻底免封号的绿色物理模拟点击内核。一手作者直供，包后续全程更新与一对一指导，是你低成本转移至韩版收割门票的首选。',
    pricing: [
      { label: '月付', duration: '1个月', price: 80 },
      { label: '年付', duration: '1年', price: 128 },
      { label: '买断', duration: '永久', price: 168 },
    ],
    currency: '¥',
    features: ['无视白屏风控', '韩版全资源制霸', '绿色彻底防封', '24H 自动捡漏'],
    badge: null,
    color: '#ec4899',
    logo: 'https://www.google.com/s2/favicons?domain=ticket.interpark.com&sz=128',
    videos: [
      '/videos/korean-interpark/promo1.mp4'
    ],
    highlights: [
      {
        title: '针对性突破平台白屏封锁',
        description: '当大批用户在国际版的“白屏”中绝望时，本工具助你优雅切换车道，降维打击所有韩版 ITP 独占及非独占演出资源，避风港里的抢票利器。',
        image: null,
      },
      {
        title: '绿色纯净内核 零封号风险',
        description: '并非那种高危协议拦截外挂。我们利用前台模拟人手点击原理开发，机制绝对纯净绿色，骗过所有的反爬虫防御与特征检测机制，确保账号安全无虞。',
        image: null,
      },
      {
        title: '24h 全天候动态捡漏',
        description: '支持精确的“选区、位置”自定，乃至随意调节切区频率。配置可在运行时实时修改，随后挂机全天候轮询锁座，连最难缠的滑块/字母验证码也自动一脚踹开。',
        image: null,
      },
      {
        title: '保姆式云报警与私密防伪',
        description: '一旦破防锁票成功，系统立刻爆出电脑提示音，并推送手机钉钉、Telegram 跨端多重锁座通知。采取独立一机一码授权制，保障纯净使用权与包身更新特权。',
        image: null,
      },
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'ticketmaster',
    name: '新加坡TicketMaster抢票捡漏插件',
    shortName: 'Ticketmaster',
    description: '全自动化彻底解放双手，结合视觉大模型 100% 自动过验证，公售与捡漏双模式制霸。',
    longDescription: '专为新加坡 TicketMaster 量身定制的全自动抢票辅助神器。搭载了尖端前沿的视觉大模型技术，彻底攻克验证码防线，达到 100% 的精准率和瞬间解包能力。产品创新性地内置了应对首发激战的「公售模式」和全天候巡视的「捡漏模式」，配合免重启实时修改选区配置功能，带给你前所未有的开挂体验。附赠保姆级图文视频教程以及一对一的定制解答维护。',
    pricing: [
      { label: '月付', duration: '1个月', price: 66 },
      { label: '年付', duration: '1年', price: 99 },
      { label: '买断', duration: '永久', price: 128 },
    ],
    currency: '¥',
    features: ['大模型 100% 解码', '双核模式（公售/捡漏）', '热更实时配置', '多端锁座级警报'],
    badge: null,
    color: '#3b82f6',
    logo: 'https://www.google.com/s2/favicons?domain=www.ticketmaster.sg&sz=128',
    videos: [
      '/videos/ticketmaster/promo1.mp4'
    ],
    highlights: [
      {
        title: '视觉大模型降维打击',
        description: '不是传统的落后识别技术，我们直接接入超级视觉大模型：识别准确率高达 100%！在验证码弹出瞬间即可实现毫秒级自动填入，保障抢票锁座不卡任何流程的脖子。',
        image: null,
      },
      {
        title: '双轨制核动力架构',
        description: '同时植入了暴力高频的「公售模式」，和稳定持久的 24h「捡漏模式」！从热度刚开的第一秒抢购到深夜持续值守，都能智能采取最高效的策略。',
        image: null,
      },
      {
        title: '无缝热更加精准选区',
        description: '支持精确自定义你要猎杀的黄金区域，更爽的是：配置表全部支持实时保存热更新。再也不用每次关掉程序重新启动，刷新页面即可直接生效你的新猎物区间。',
        image: null,
      },
      {
        title: '穿透级跨端锁座唤醒',
        description: '锁票的瞬间就是胜利！除了你的电脑会发出夺命持久的高分贝声响防漏付外，还可以配置手机钉钉甚至非大陆友好的 Telegram 推送。哪怕是在深更半夜熟睡也能立刻被唤醒清空购物车！',
        image: null,
      },
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'ticketlink',
    name: '韩国 Ticketlink 抢票捡漏插件',
    shortName: 'Ticketlink',
    description: '覆盖韩国 Ticketlink 公售与捡漏场景，支持自动刷新、精准选区、锁座提醒和一机一码授权。',
    longDescription: '专为韩国 Ticketlink 打造的全自动抢票捡漏插件，覆盖热门演唱会、音乐剧及体育赛事等常见购票场景。插件支持公售高频抢票与 24 小时自动捡漏两种使用方式，可按区域、席位条件和刷新频率进行灵活配置，锁到票后通过浏览器声音、钉钉和 Telegram 多端提醒。采用前台模拟点击与一机一码授权机制，搭配详细安装教程和持续维护，适合需要长期稳定蹲守 Ticketlink 余票的用户。',
    pricing: [
      { label: '月付', duration: '1个月', price: 80 },
      { label: '年付', duration: '1年', price: 128 },
      { label: '买断', duration: '永久', price: 168 },
    ],
    currency: '¥',
    features: ['韩国场次覆盖', '公售/捡漏双模式', '精确选区配置', '多端锁座提醒'],
    badge: '新品',
    color: '#ef4444',
    logo: 'https://www.google.com/s2/favicons?domain=www.ticketlink.co.kr&sz=128',
    videos: [
      '/videos/ticketlink/promo1.mp4'
    ],
    highlights: [
      {
        title: 'Ticketlink 专属流程适配',
        description: '围绕韩国 Ticketlink 的购票路径做针对性适配，从进入场次、刷新票池到尝试锁座都能自动衔接，减少手动切换页面与重复点击带来的失误。',
        image: null,
      },
      {
        title: '公售与捡漏双模式切换',
        description: '开售瞬间可使用高频公售模式抢占先机，错过首轮也能切换为 24 小时捡漏巡航，持续捕捉退票和未付款释放出来的余票。',
        image: null,
      },
      {
        title: '精细化区域与席位配置',
        description: '支持提前设置目标区域、席位偏好与刷新节奏，配置可根据实际票池变化灵活调整，让插件集中火力处理真正想要的位置。',
        image: null,
      },
      {
        title: '锁座提醒与专属维护',
        description: '成功锁票后会通过电脑声音、钉钉和 Telegram 多端提醒，避免错过付款窗口。购买后提供激活码、使用教程和后续版本维护。',
        image: null,
      },
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
  {
    id: 'cityline',
    name: 'Cityline 捡漏抢票插件',
    shortName: 'Cityline',
    description: '全程无需手动干预的巅峰引擎，毫秒级碾压手速，死磕直到锁心仪门票。',
    longDescription: '这不仅仅是一个脚本，而是一个能完全取代双手的全自动 Cityline 极速战士。针对 Cityline 繁琐的购票流程进行了全方位降维打击：从进入页面开始，选购、排队、抢票模式均比人类肌肉记忆快上无数个量级，全程 100% 免干预自动化运行直至锁票成功。完美解决公售与漫长捡漏的持久战需求，附带独家睡眠级多端强提醒，一站式解决您的抢票难题。',
    pricing: [
      { label: '月付', duration: '1个月', price: 66 },
      { label: '年付', duration: '1年', price: 99 },
      { label: '买断', duration: '永久', price: 128 },
    ],
    currency: '¥',
    features: ['100% 全自动免干预', '降维碾压手速', '死磕直至出票', '多端唤醒级通知'],
    badge: null,
    color: '#8b5cf6',
    logo: 'https://www.google.com/s2/favicons?domain=www.cityline.com&sz=128',
    videos: [
      '/videos/cityline/promo1.mp4'
    ],
    highlights: [
      {
        title: '全自动无痛接管',
        description: '一句话暴击痛点：全程无需任何手动操作！从开局到终点，它就像一个全不知疲倦的数字劳工，替你完成每一次高频刷票与枯燥排队，直到帮你把票死死锁在购物车内！',
        image: null
      },
      {
        title: '毫秒级超频手速',
        description: '人的反应是有极限的，但代码没有。在残酷的公售抢票模式下，插件能以超越人类视觉和手速数十倍的极速执行拦截与下单动作，快准狠，别人没看到票就已经结束战斗。',
        image: null
      },
      {
        title: '防掉线死磕到底',
        description: '不论是前期高峰挤不进去，还是后期的漫长蹲守捡漏，插件能够稳定维持运行状态并在票池翻腾。一旦有一张余票退回流出，瞬间捕获长驱直入锁定，直至成功绝不罢休。',
        image: null
      },
      {
        title: '全维度锁座级唤醒',
        description: '锁票的瞬间就是狂欢！哪怕你在睡觉，一旦锁座成功，电脑直接持续爆出高分贝系统声音。同时你的手机钉钉、Telegram 亦会同步疯狂推送跨端锁座通知，绝对不怕漏付。',
        image: null
      }
    ],
    testimonialVideo: '/videos/interpark/testimonial.mp4',
  },
];

export const features = [
  {
    icon: 'Zap',
    title: '极速抢票',
    description: '公售会员购捡漏均适用，毫秒级响应，在票务开售瞬间自动抢购',
  },
  {
    icon: 'Shield',
    title: '安全稳定',
    description: '防检测机制，模拟真实用户行为，降低封号风险',
  },
  {
    icon: 'Globe',
    title: '多平台覆盖',
    description: '支持韩国、香港、新加坡等多个热门票务平台',
  },
  {
    icon: 'Headphones',
    title: '专属客服',
    description: '一对一技术支持，购买后提供使用教程和指导',
  },
];

export const faqs = [
  {
    question: '购买后如何使用？',
    answer: '购买成功后会发送激活码和详细使用教程。按照教程安装 Chrome 插件并输入激活码即可使用。',
  },
  {
    question: '支持哪些支付方式？',
    answer: '支持微信支付和支付宝转账，添加客服微信即可完成购买。',
  },
  {
    question: '激活码可以用多久？',
    answer: '激活码为永久有效，一次购买终身使用。后续更新免费。',
  },
  {
    question: '如果遇到问题怎么办？',
    answer: '您可以通过 Telegram 或微信联系我们的客服，我们会第一时间为您解决问题。',
  },
  {
    question: '是否支持退款？',
    answer: '由于数字商品的特殊性，激活码发出后不支持退款。购买前请仔细阅读产品说明。',
  },
  {
    question: '一个激活码可以用在几台设备上？',
    answer: '每个激活码支持在一台设备上使用。如果需要更换设备，请联系客服处理。',
  },
];
