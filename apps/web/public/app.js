const state = {
  books: [],
  query: "",
  status: "all",
  category: "all",
  sort: "recent",
};

const elements = {
  grid: document.querySelector("#bookGrid"),
  statusLine: document.querySelector("#statusLine"),
  template: document.querySelector("#bookCardTemplate"),
  totalBooks: document.querySelector("#totalBooks"),
  finishedBooks: document.querySelector("#finishedBooks"),
  readingBooks: document.querySelector("#readingBooks"),
  highlightCount: document.querySelector("#highlightCount"),
  searchInput: document.querySelector("#searchInput"),
  statusFilter: document.querySelector("#statusFilter"),
  categoryFilter: document.querySelector("#categoryFilter"),
  sortSelect: document.querySelector("#sortSelect"),
  refreshButton: document.querySelector("#refreshButton"),
};

elements.searchInput.addEventListener("input", (event) => {
  state.query = event.target.value.trim().toLowerCase();
  render();
});

elements.statusFilter.addEventListener("change", (event) => {
  state.status = event.target.value;
  render();
});

elements.categoryFilter.addEventListener("change", (event) => {
  state.category = event.target.value;
  render();
});

elements.sortSelect.addEventListener("change", (event) => {
  state.sort = event.target.value;
  render();
});

elements.refreshButton.addEventListener("click", () => {
  loadBooks({ refresh: true });
});

loadBooks();

async function loadBooks({ refresh = false } = {}) {
  setStatus("正在读取书架...");
  elements.refreshButton.disabled = true;
  try {
    const response = await fetch(`/api/books${refresh ? "?refresh=1" : ""}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "读取失败");
    }
    state.books = Array.isArray(data.books) ? data.books : [];
    hydrateCategories();
    render();
    setStatus(`已载入 ${state.books.length} 本书${data.cached ? "，来自缓存" : ""}`);
  } catch (error) {
    state.books = [];
    render();
    setStatus(error instanceof Error ? error.message : "读取失败");
  } finally {
    elements.refreshButton.disabled = false;
  }
}

function hydrateCategories() {
  const selected = elements.categoryFilter.value;
  const categories = [...new Set(state.books.flatMap((book) => book.categories || []))]
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));

  elements.categoryFilter.innerHTML = '<option value="all">全部分类</option>';
  for (const category of categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    elements.categoryFilter.append(option);
  }
  if (categories.includes(selected)) {
    elements.categoryFilter.value = selected;
  }
}

function render() {
  const books = filteredBooks();
  renderStats(state.books);
  renderBooks(books);
}

function filteredBooks() {
  const query = state.query;
  return [...state.books]
    .filter((book) => {
      if (state.status !== "all" && book.status !== state.status) return false;
      if (state.category !== "all" && !(book.categories || []).includes(state.category)) return false;
      if (!query) return true;
      const haystack = [book.title, book.author, ...(book.categories || [])].join(" ").toLowerCase();
      return haystack.includes(query);
    })
    .sort(sortBooks);
}

function sortBooks(a, b) {
  if (state.sort === "progress") return b.progress - a.progress;
  if (state.sort === "highlights") return b.highlightCount - a.highlightCount;
  if (state.sort === "title") return a.title.localeCompare(b.title, "zh-Hans-CN");
  return b.sort - a.sort;
}

function renderStats(books) {
  elements.totalBooks.textContent = String(books.length);
  elements.finishedBooks.textContent = String(books.filter((book) => book.status === "读完").length);
  elements.readingBooks.textContent = String(books.filter((book) => book.status === "在读").length);
  elements.highlightCount.textContent = String(
    books.reduce((sum, book) => sum + (book.highlightCount || 0), 0),
  );
}

function renderBooks(books) {
  elements.grid.innerHTML = "";
  if (!books.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "没有匹配的书。";
    elements.grid.append(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const book of books) {
    fragment.append(createBookCard(book));
  }
  elements.grid.append(fragment);
}

function createBookCard(book) {
  const node = elements.template.content.firstElementChild.cloneNode(true);
  const coverLink = node.querySelector(".cover-link");
  const cover = node.querySelector(".cover");
  const fallback = node.querySelector(".cover-fallback");
  const title = node.querySelector(".book-title");
  const author = node.querySelector(".book-author");
  const status = node.querySelector(".status-badge");
  const progressText = node.querySelector(".progress-text");
  const progressRing = node.querySelector(".progress-ring");
  const categories = node.querySelector(".category-list");
  const highlights = node.querySelector(".highlight-meta");
  const thoughts = node.querySelector(".thought-meta");

  coverLink.href = book.wereadUrl || book.notionUrl || "#";
  title.textContent = book.title;
  author.textContent = book.author || "未知作者";
  status.textContent = book.status || "未读";
  status.dataset.status = book.status || "未读";

  const progress = Math.round((book.progress || 0) * 100);
  progressText.textContent = `${progress}%`;
  progressRing.style.setProperty("--progress", `${progress}%`);
  progressRing.title = `阅读进度 ${progress}%`;

  if (book.cover) {
    cover.src = book.cover;
    cover.alt = `${book.title} 封面`;
    cover.addEventListener("error", () => {
      cover.remove();
      fallback.style.display = "block";
    });
  } else {
    cover.remove();
    fallback.style.display = "block";
  }

  for (const category of (book.categories || []).slice(0, 3)) {
    const tag = document.createElement("span");
    tag.className = "category";
    tag.textContent = category;
    categories.append(tag);
  }

  highlights.textContent = `${book.highlightCount || 0} 条划线`;
  thoughts.textContent = `${book.thoughtCount || 0} 个想法`;

  return node;
}

function setStatus(message) {
  elements.statusLine.textContent = message;
}
