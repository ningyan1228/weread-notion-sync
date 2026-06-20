declare const Netlify: {
  env?: {
    get(name: string): string | undefined;
  };
};

type NotionRichText = {
  plain_text?: string;
};

type NotionProperty = {
  type?: string;
  title?: NotionRichText[];
  rich_text?: NotionRichText[];
  number?: number | null;
  url?: string | null;
  select?: { name?: string; color?: string } | null;
  status?: { name?: string; color?: string } | null;
  multi_select?: Array<{ name?: string; color?: string }>;
  date?: { start?: string | null } | null;
  files?: Array<{
    type?: string;
    name?: string;
    external?: { url?: string };
    file?: { url?: string };
  }>;
};

type NotionPage = {
  id: string;
  cover?: {
    type?: string;
    external?: { url?: string };
    file?: { url?: string };
  } | null;
  url?: string;
  properties?: Record<string, NotionProperty>;
};

type Book = {
  id: string;
  title: string;
  author: string;
  cover: string;
  status: string;
  progress: number;
  readingTime: string;
  categories: string[];
  highlightCount: number;
  thoughtCount: number;
  rating: number | null;
  isbn: string;
  wereadUrl: string;
  notionUrl: string;
  lastSyncedAt: string;
  sort: number;
};

const NOTION_VERSION = "2026-03-11";
const CACHE_TTL_MS = 10 * 60 * 1000;

let cachedAt = 0;
let cachedBooks: Book[] | null = null;

export default async (req: Request) => {
  if (req.method !== "GET") {
    return json({ error: "Method not allowed" }, 405);
  }

  try {
    const now = Date.now();
    const force = new URL(req.url).searchParams.get("refresh") === "1";
    if (!force && cachedBooks && now - cachedAt < CACHE_TTL_MS) {
      return json({ books: cachedBooks, cached: true, updatedAt: new Date(cachedAt).toISOString() });
    }

    const token = getEnv("NOTION_TOKEN");
    const dataSourceId = await resolveDataSourceId(token);
    const pages = await queryAllPages(token, dataSourceId);
    const books = pages.map(normalizeBook).filter((book) => book.title);

    cachedBooks = books;
    cachedAt = now;

    return json({ books, cached: false, updatedAt: new Date(cachedAt).toISOString() });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return json({ error: message }, 500);
  }
};

export const config = {
  path: "/api/books",
};

async function resolveDataSourceId(token: string): Promise<string> {
  const direct = getEnv("NOTION_DATA_SOURCE_ID", false);
  if (direct) {
    return extractNotionId(direct);
  }

  const databaseInput = getEnv("NOTION_DATABASE_ID", false) || getEnv("NOTION_PAGE", false);
  if (!databaseInput) {
    throw new Error("Missing NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID");
  }

  const databaseId = extractNotionId(databaseInput);
  const database = await notionRequest(token, `databases/${databaseId}`, "GET");
  const sources = database.data_sources || [];
  if (!sources.length) {
    throw new Error("No data source found under this Notion database");
  }
  return sources[0].id;
}

async function queryAllPages(token: string, dataSourceId: string): Promise<NotionPage[]> {
  const pages: NotionPage[] = [];
  let startCursor: string | undefined;

  do {
    const body: Record<string, unknown> = {
      page_size: 100,
      sorts: [{ property: "Sort", direction: "descending" }],
    };
    if (startCursor) {
      body.start_cursor = startCursor;
    }

    const data = await notionRequest(token, `data_sources/${dataSourceId}/query`, "POST", body);
    pages.push(...(data.results || []));
    startCursor = data.has_more ? data.next_cursor : undefined;
  } while (startCursor);

  return pages;
}

async function notionRequest(
  token: string,
  path: string,
  method: "GET" | "POST",
  body?: unknown,
) {
  const response = await fetch(`https://api.notion.com/v1/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "Notion-Version": NOTION_VERSION,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.message || `Notion API failed: ${response.status}`);
  }
  return data;
}

function normalizeBook(page: NotionPage): Book {
  const props = page.properties || {};
  return {
    id: page.id,
    title: textProp(props["书名"]),
    author: textProp(props["作者"]),
    cover: coverUrl(page, props["封面"]),
    status: optionProp(props["状态"]),
    progress: clamp(numberProp(props["阅读进度"])),
    readingTime: textProp(props["阅读时长"]),
    categories: multiSelectProp(props["分类"]),
    highlightCount: numberProp(props["划线数量"]),
    thoughtCount: numberProp(props["想法数量"]),
    rating: nullableNumberProp(props["评分"]),
    isbn: textProp(props["ISBN"]),
    wereadUrl: urlProp(props["微信读书链接"]),
    notionUrl: page.url || "",
    lastSyncedAt: dateProp(props["最后同步时间"]),
    sort: numberProp(props["Sort"]),
  };
}

function textProp(prop?: NotionProperty): string {
  if (!prop) return "";
  const rich = prop.title || prop.rich_text || [];
  return rich.map((item) => item.plain_text || "").join("");
}

function numberProp(prop?: NotionProperty): number {
  return nullableNumberProp(prop) ?? 0;
}

function nullableNumberProp(prop?: NotionProperty): number | null {
  return typeof prop?.number === "number" ? prop.number : null;
}

function optionProp(prop?: NotionProperty): string {
  return prop?.status?.name || prop?.select?.name || "";
}

function multiSelectProp(prop?: NotionProperty): string[] {
  return (prop?.multi_select || []).map((item) => item.name || "").filter(Boolean);
}

function urlProp(prop?: NotionProperty): string {
  return prop?.url || "";
}

function dateProp(prop?: NotionProperty): string {
  return prop?.date?.start || "";
}

function coverUrl(page: NotionPage, prop?: NotionProperty): string {
  const pageCover = page.cover?.external?.url || page.cover?.file?.url;
  if (pageCover) return pageCover;
  const file = prop?.files?.[0];
  if (file?.external?.url) return file.external.url;
  if (file?.file?.url) return file.file.url;
  if (prop?.url) return prop.url;
  return "";
}

function clamp(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(Math.max(value, 0), 1);
}

function extractNotionId(value: string): string {
  const match = value.match(/[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/i);
  if (!match) {
    throw new Error("Invalid Notion database or data source ID");
  }
  return match[0];
}

function getEnv(name: string, required = true): string {
  const value = Netlify.env?.get(name) || "";
  if (!value && required) {
    throw new Error(`Missing environment variable: ${name}`);
  }
  return value.trim();
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60, s-maxage=600",
    },
  });
}
