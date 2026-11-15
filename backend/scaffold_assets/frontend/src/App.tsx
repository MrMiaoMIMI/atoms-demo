import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  Icon,
  InlineNotice,
  PageHeader,
  Skeleton,
  Toaster,
} from "./ui";

const TITLE = __TITLE_JSON__;

const HIGHLIGHTS = [
  {
    icon: "dashboard" as const,
    title: "有设计系统的起点",
    copy: "统一的排版、配色、间距与组件，替换 starter 内容即可开始。",
  },
  {
    icon: "shield" as const,
    title: "可交互、可访问",
    copy: "按钮、表单、弹窗与状态都已处理 hover、focus 与键盘操作。",
  },
  {
    icon: "zap" as const,
    title: "构建即预览",
    copy: "修改 frontend/src/App.tsx 与 styles.css，右侧预览会同步更新。",
  },
];

export default function App() {
  return (
    <div className="app">
      <div className="ds-container app__container">
        <PageHeader
          eyebrow="NEW PROJECT"
          title={TITLE}
          description="这是一个可运行的起点。告诉 Alex 你的需求，或直接编辑 frontend/src/App.tsx。"
          actions={
            <>
              <Button variant="secondary" icon="edit">
                编辑代码
              </Button>
              <Button icon="sparkles">开始定制</Button>
            </>
          }
        />

        <div className="ds-grid ds-grid--3">
          {HIGHLIGHTS.map((item) => (
            <Card key={item.title} interactive>
              <CardBody>
                <div className="ds-stack" style={{ gap: 12 }}>
                  <span className="ds-empty__icon">
                    <Icon name={item.icon} size={20} />
                  </span>
                  <div className="ds-stack" style={{ gap: 6 }}>
                    <div className="ds-card__title">{item.title}</div>
                    <p className="ds-small">{item.copy}</p>
                  </div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>

        <Card>
          <CardBody>
            <div className="ds-stack" style={{ gap: 12 }}>
              <div className="ds-row ds-row--between">
                <span className="ds-card__title">状态与反馈</span>
                <Badge tone="success" dot>
                  Live
                </Badge>
              </div>
              <Skeleton width="58%" height={14} />
              <InlineNotice
                tone="info"
                icon={<Icon name="info" size={16} />}
              >
                用 InlineNotice 展示提示、警告或错误；用 Skeleton 表达加载中。
              </InlineNotice>
            </div>
          </CardBody>
        </Card>

        <Card>
          <div className="ds-row ds-row--between" style={{ padding: "18px 24px 0" }}>
            <Badge tone="accent" dot>
              Scaffold ready
            </Badge>
            <span className="ds-small">React 18 · TypeScript · Vite</span>
          </div>
          <EmptyState
            icon="sparkles"
            title="准备就绪"
            description="设计系统与 UI 组件已经就位。描述你的产品，Alex 会在此基础上实现页面与交互。"
            action={
              <Button variant="soft" icon="arrowRight">
                描述需求
              </Button>
            }
          />
        </Card>
      </div>
      <Toaster />
    </div>
  );
}
