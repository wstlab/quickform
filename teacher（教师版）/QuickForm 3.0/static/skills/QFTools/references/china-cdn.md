# 中国大陆可用 CDN 资源清单

> 所有资源均通过 jsdelivr.net 加载，在中国大陆访问稳定。

## CSS 框架

### Tailwind CSS（推荐，最常用）
```html
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```

### Bootstrap 5
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/css/bootstrap.min.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/js/bootstrap.bundle.min.js"></script>
```

---

## JavaScript 框架

### Alpine.js（轻量响应式，推荐用于教学工具）
```html
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
```

### Vue 3（CDN 模式）
```html
<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
```

---

## 图表库

### ECharts 5（推荐，百度出品，国内访问极快）
```html
<!-- 完整版 -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<!-- 精简版（无地图） -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.common.min.js"></script>
```

### Chart.js（备选）
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
```

---

## 图标库

### Font Awesome 6（免费版）
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6/css/all.min.css">
```

### Remix Icon（国产图标库，备选）
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/remixicon@4/fonts/remixicon.css">
```

---

## 动画库

### Animate.css
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/animate.css@4/animate.min.css">
```

---

## 字体（注意：Google Fonts 在国内无法访问）

### 推荐方案：使用系统字体栈
```css
body {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", 
               "Helvetica Neue", Arial, sans-serif;
}
```

### 或使用字体 CDN（中国可用）
```html
<!-- 思源黑体 via jsdelivr -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5/index.min.css">
```

---

## 不可用资源（避免使用）

❌ `fonts.googleapis.com` — Google Fonts，国内无法访问
❌ `ajax.googleapis.com` — Google CDN，国内无法访问
❌ `unpkg.com` — 部分地区不稳定
❌ `cdnjs.cloudflare.com` — Cloudflare CDN，部分地区不稳定
❌ `stackpath.bootstrapcdn.com` — 国内访问慢
