# 网页开发基础

了解网页开发的基础知识，有助于我们做出更多有创意的应用。

## HTML入门

1.HTML的标签

HTML（超文本标记语言）是网页的骨架，它使用标签来定义网页的结构。

基础HTML结构：

```
html
<!DOCTYPE html>
<html>
<head>
    <title>我的第一个网页</title>
</head>
<body>
    <h1>欢迎来到我的网页</h1>
    <p>这是我的第一个段落。</p>
</body>
</html>

```

常用HTML标签：

<h1>到<h6>：标题标签

<p>：段落标签

<a href="...">：链接标签

<img src="..." alt="...">：图片标签

<div>和<span>：容器标签

2.CSS样式表



3.js脚本


## 前端交互知识

根据代码运行的位置，Web应用分为前端和后端技术。网页的交互技术，其实指的就是前端和后端的交互。需要强调的是，浏览器的数据传输（即前后端交互）经历了好几个阶段。最初使用“Form”，后来使用XMLHttpRequest，现在则基本上使用Fetch API。具体请参考“学习资料”中的“网页开发基础”。

### 第一代：原生 Form 表单提交

Form 表单是“Web 1.0”时代唯一的数据提交方式，只适合简单的登录、注册，完全无法做复杂交互。

范例代码

```html

<!-- 最原始的数据提交方式 -->
<form action="/submit" method="POST">
  <input name="username" />
  <button type="submit">提交</button>
</form>
```

### 第二代：XMLHttpRequest

为解决“Form”必须刷新页面的致命问题，让前端可以不刷新页面和服务器通信，2005年，随着“AJAX”概念的提出，XMLHttpRequest开始普及，开启了 Web 2.0 时代。

范例代码

```javascript

// 经典 XHR 写法（繁琐）
const xhr = new XMLHttpRequest();
xhr.open('POST', '/submit', true); // true = 异步

xhr.onload = function() {
  if(xhr.status === 200) {
    console.log(xhr.responseText); // 局部更新页面，不刷新
  }
};

xhr.send('username=test');

```

### 第三代：Fetch API

“XMLHttpRequest”的设计非常繁琐、不直观，编程难度很大。“Fetch API”于2011年首次提出，2015年被 WHATWG 正式标准化，并在同年开始被主流浏览器原生支持。

范例代码：

```javascript

// 现代简洁写法
async function postData() {
  const res = await fetch('/submit', {
    method: 'POST',
    body: JSON.stringify({ username: 'test' }),
    headers: { 'Content-Type': 'application/json' }
  });
  const data = await res.json();
  console.log(data);
}
```

### 表单基础知识

表单的地址和方法：POST、GET


## 数据库基础

数据库基本知识








