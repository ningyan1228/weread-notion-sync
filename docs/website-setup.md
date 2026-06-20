# 网站部署说明

这个网站使用：

```text
静态前端 + Netlify Function + Notion API
```

前端文件在：

```text
apps/web/public
```

Netlify Function 在：

```text
apps/web/netlify/functions/books.ts
```

## 数据流

```text
浏览器
  -> /api/books
  -> Netlify Function
  -> Notion API
  -> 返回书籍 JSON
```

`NOTION_TOKEN` 只保存在 Netlify 环境变量里，不会暴露给浏览器。

## Netlify 环境变量

在 Netlify 站点里进入：

```text
Site configuration -> Environment variables
```

添加：

```text
NOTION_TOKEN=你的 Notion Integration Token
NOTION_DATA_SOURCE_ID=你的 Notion data source ID
```

如果你没有 `NOTION_DATA_SOURCE_ID`，也可以填：

```text
NOTION_DATABASE_ID=你的 Notion database ID
```

可选：

```text
SITE_TITLE=我的微信读书书架
SITE_DESCRIPTION=从微信读书同步而来的个人阅读记录
```

## Netlify 构建配置

仓库里已经有根目录 `netlify.toml`：

```toml
[build]
  base = "apps/web"
  command = "echo No build step required"
  publish = "public"

[functions]
  directory = "netlify/functions"
  node_bundler = "esbuild"
```

在 Netlify 从 GitHub 导入仓库时，如果它自动读取 `netlify.toml`，不用手动改。

如果需要手动填写：

```text
Base directory: apps/web
Build command: echo No build step required
Publish directory: public
Functions directory: netlify/functions
```

## 本地运行

需要先安装 Node.js 和 Netlify CLI。

```bash
cd apps/web
npm install
npm run dev
```

本地 `.env` 可以参考：

```text
apps/web/.env.example
```

## 页面功能

第一版已经包含：

- 总书数、读完、在读、划线数统计
- 书名 / 作者 / 分类搜索
- 状态筛选
- 分类筛选
- 最近更新、阅读进度、划线数量、书名排序
- 书籍封面卡片
- 阅读进度环
- 划线数量和想法数量

## 隐私说明

网站第一版只展示书籍摘要，不展示具体划线和想法正文。

公开展示的信息包括：

- 书名
- 封面
- 作者
- 分类
- 阅读状态
- 阅读进度
- 阅读时长
- 划线数量
- 想法数量

如果后续要公开具体划线内容，建议增加单独开关。
