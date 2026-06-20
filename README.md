# WeRead Notion Sync

把微信读书的书籍、阅读进度、划线和想法同步到 Notion，生成类似 Gallery 书架的笔记页面。

这个项目的使用方式对普通用户尽量友好：Fork 仓库，填写 GitHub Secrets，手动运行一次 workflow，之后就可以定时同步。

## 效果

你可以在 Notion 里创建一个数据库 Gallery 视图，卡片展示：

- 书籍封面
- 书名
- 阅读状态
- 阅读进度
- 分类标签
- 作者、ISBN、评分、微信读书链接

点进每本书后，页面内会按章节写入划线和想法。

## 准备 3 个值

| 名称 | 用途 | 是否必填 |
| --- | --- | --- |
| `WEREAD_API_KEY` | 微信读书 Gateway API Key，用于读取微信读书数据 | 必填 |
| `NOTION_TOKEN` | Notion Integration Token，用于写入 Notion | 必填 |
| `NOTION_PAGE` | Notion 数据库页面链接、数据库 ID 或 data source ID | 必填 |

如果复制时带了空格或换行，脚本会自动清理。格式明显不对时，GitHub Actions 会显示红色错误。

## 不会做 Notion 数据库怎么办

不用手工建字段。你只需要：

1. 在 Notion 新建一个空白页面，名字可以叫 `微信读书笔记`。
2. 把 Notion Integration 邀请进这个空白页面。
3. 复制这个空白页面链接，先填到 GitHub Secret：`NOTION_PAGE`。
4. 先只配置这两个 Secret：
   - `NOTION_TOKEN`
   - `NOTION_PAGE`
5. 到 GitHub Actions 手动运行 `weread notion sync`，`command` 选择 `setup`。
6. setup 成功后，日志里会输出 `URL=` 或 `DATABASE_ID=`。
7. 回到 GitHub Secrets，把 `NOTION_PAGE` 改成 setup 输出的 `URL` 或 `DATABASE_ID`。
8. 再补上 `WEREAD_API_KEY`，运行 `command=sync`。

这样数据库和字段会自动创建。

## 手动创建 Notion 模板字段

请在 Notion 建一个数据库，建议使用 Gallery 视图。至少保留下面这些字段：

| 字段名 | 类型 | 是否必需 | 说明 |
| --- | --- | --- | --- |
| `书名` | Title | 必需 | 页面标题，可以叫其他名字，只要是 Title 类型 |
| `BookId` | Rich text | 必需 | 微信读书书籍 ID，用于去重 |
| `Sort` | Number | 必需 | 微信读书同步游标，用于增量同步 |
| `作者` | Rich text | 可选 | 作者 |
| `封面` | URL 或 Files | 可选 | 书籍封面 |
| `状态` | Status / Select | 可选 | 在读、读完 |
| `阅读进度` | Number | 可选 | 建议设置成 Percent |
| `阅读时长` | Rich text | 可选 | 例如 3时20分 |
| `分类` | Multi-select | 可选 | 微信读书分类 |
| `ISBN` | Rich text | 可选 | ISBN |
| `评分` | Number | 可选 | 微信读书评分 |
| `微信读书链接` | URL | 可选 | 跳转到微信读书网页版 |
| `最后同步时间` | Date | 可选 | 本次同步时间 |
| `划线数量` | Number | 可选 | 本书划线数量 |
| `想法数量` | Number | 可选 | 本书想法数量 |

Gallery 视图建议：

- Card preview 选择页面封面
- Card size 选择 Medium
- Properties 显示 `状态`、`阅读进度`、`分类`
- Sort 按 `Sort` 降序

## GitHub Actions 使用

1. Fork 这个仓库。
2. 打开 Fork 后的仓库，进入 `Settings -> Secrets and variables -> Actions`。
3. 新增下面 3 个 Repository secret：

| Secret 名称 | 填写内容 |
| --- | --- |
| `WEREAD_API_KEY` | 微信读书 API Key |
| `NOTION_TOKEN` | Notion Integration Token |
| `NOTION_PAGE` | Notion 数据库页面链接、数据库 ID 或 data source ID |

4. 进入 `Actions`，选择 `weread notion sync`。
5. 如果还没建数据库，先点击 `Run workflow`，`command` 选择 `setup`。
6. setup 完成后，把日志里的 `URL` 或 `DATABASE_ID` 填回 `NOTION_PAGE`。
7. 再点击 `Run workflow`，`command` 选择 `sync`。

默认每天北京时间 08:00 自动同步一次。

## 本地运行

```bash
python -m pip install -e .
cp .env.example .env
weread-notion sync
```

Windows PowerShell 可以手动设置环境变量：

```powershell
$env:WEREAD_API_KEY="你的微信读书 API Key"
$env:NOTION_TOKEN="你的 Notion Token"
$env:NOTION_PAGE="你的 Notion 数据库链接"
weread-notion sync
```

## 同步策略

脚本会读取 Notion 数据库中最大的 `Sort`，只同步微信读书里 `Sort` 更新的书。

如果一本书已存在，脚本会更新数据库属性，并只替换由同步脚本管理的内容区。为了减少误删，脚本会写入清晰的同步标记：

```text
--- weread-notion-sync:begin ---
--- weread-notion-sync:end ---
```

请不要在这两个标记之间写自己的长期笔记。你可以在标记外自由写内容。

## 安全提醒

`WEREAD_API_KEY` 和 `NOTION_TOKEN` 都可以读取或写入你的私人数据，不要写到公开代码里，也不要发给别人。
