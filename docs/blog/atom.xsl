<?xml version="1.0" encoding="utf-8"?>
<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0

Atom 1.0 Browser Stylesheet for Zenzic Blog
Renders a human-readable HTML page when the Atom feed is opened in a browser.
Feed readers receive the raw XML and ignore this stylesheet.
-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom"
  exclude-result-prefixes="atom">

  <xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:legacy-compat"/>

  <xsl:template match="/">
    <html lang="en" data-md-color-scheme="slate">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title><xsl:value-of select="/atom:feed/atom:title"/> — Atom Feed</title>
        <link rel="stylesheet" href="/assets/css/zenzic-tailwind.min.css"/>
        <link rel="stylesheet" href="/assets/css/extra.css"/>
        <style>
          :root {
            --zz-rss-bg:        #0d1117;
            --zz-rss-surface:   #161b22;
            --zz-rss-border:    #30363d;
            --zz-rss-text:      #c9d1d9;
            --zz-rss-muted:     #8b949e;
            --zz-rss-accent:    #10b981;
            --zz-rss-link:      #58a6ff;
            --zz-rss-badge-bg:  #1f2937;
            --zz-rss-radius:    8px;
          }
          *, *::before, *::after { box-sizing: border-box; }
          body {
            margin: 0;
            background: var(--zz-rss-bg);
            color: var(--zz-rss-text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            font-size: 15px;
            line-height: 1.6;
          }
          .rss-header {
            background: var(--zz-rss-surface);
            border-bottom: 1px solid var(--zz-rss-border);
            padding: 1.5rem 2rem;
            display: flex;
            align-items: center;
            gap: 1.5rem;
            flex-wrap: wrap;
          }
          .rss-logo { width: 40px; height: 40px; }
          .rss-header-text h1 { margin: 0 0 0.15rem; font-size: 1.25rem; font-weight: 700; color: #fff; }
          .rss-header-text p  { margin: 0; font-size: 0.85rem; color: var(--zz-rss-muted); }
          .rss-subscribe-btn {
            margin-left: auto;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1.1rem;
            background: #f59e0b;
            color: #000;
            font-size: 0.82rem;
            font-weight: 600;
            border-radius: 20px;
            text-decoration: none;
            white-space: nowrap;
          }
          .rss-subscribe-btn:hover { opacity: 0.85; }
          .rss-container { max-width: 820px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
          .rss-notice {
            background: var(--zz-rss-badge-bg);
            border: 1px solid var(--zz-rss-border);
            border-radius: var(--zz-rss-radius);
            padding: 0.8rem 1.1rem;
            margin-bottom: 2rem;
            font-size: 0.83rem;
            color: var(--zz-rss-muted);
          }
          .rss-notice strong { color: var(--zz-rss-text); }
          .rss-notice code { background: #0d1117; padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.85em; }
          .rss-notice a { color: var(--zz-rss-link); }
          .rss-meta { margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--zz-rss-border); }
          .rss-meta dl { display: grid; grid-template-columns: max-content 1fr; column-gap: 1.25rem; row-gap: 0.3rem; margin: 0; }
          .rss-meta dt { color: var(--zz-rss-muted); font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding-top: 0.05rem; }
          .rss-meta dd { margin: 0; font-size: 0.85rem; }
          .rss-meta a { color: var(--zz-rss-link); text-decoration: none; }
          .rss-item { padding: 1.5rem 0; border-bottom: 1px solid var(--zz-rss-border); }
          .rss-item:last-child { border-bottom: none; }
          .rss-item-title { margin: 0 0 0.4rem; font-size: 1.05rem; font-weight: 700; }
          .rss-item-title a { color: #fff; text-decoration: none; }
          .rss-item-title a:hover { color: var(--zz-rss-accent); }
          .rss-item-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; margin-bottom: 0.75rem; font-size: 0.78rem; color: var(--zz-rss-muted); }
          .sep { opacity: 0.4; }
          .rss-category { display: inline-block; padding: 0.1rem 0.55rem; background: var(--zz-rss-badge-bg); border: 1px solid var(--zz-rss-border); border-radius: 20px; font-size: 0.72rem; color: var(--zz-rss-muted); }
          .rss-item-description { font-size: 0.88rem; color: var(--zz-rss-text); line-height: 1.65; margin: 0 0 0.85rem; }
          .rss-item-description p { margin: 0 0 0.5em; }
          .rss-item-description code { background: var(--zz-rss-badge-bg); padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.82em; }
          .rss-read-more { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.8rem; font-weight: 600; color: var(--zz-rss-accent); text-decoration: none; }
          .rss-read-more:hover { text-decoration: underline; }
          .rss-read-more::after { content: " →"; }
          .rss-footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--zz-rss-border); font-size: 0.78rem; color: var(--zz-rss-muted); text-align: center; }
          .rss-footer a { color: var(--zz-rss-link); text-decoration: none; }
          .rss-footer p { margin: 0.3rem 0; }
        </style>
      </head>
      <body>
        <header class="rss-header">
          <img class="rss-logo" src="/assets/brand/svg/zenzic-icon.svg" alt="Zenzic logo"/>
          <div class="rss-header-text">
            <h1><xsl:value-of select="/atom:feed/atom:title"/></h1>
            <p><xsl:value-of select="/atom:feed/atom:subtitle"/></p>
          </div>
          <a class="rss-subscribe-btn" href="/blog/atom.xml">&#9883; Subscribe via Atom</a>
        </header>
        <main class="rss-container">
          <div class="rss-notice">
            <strong>This is a live Atom feed (RFC 4287).</strong>
            Copy <code><xsl:value-of select="/atom:feed/atom:link[@rel='self']/@href"/></code> into your feed reader.
            An <a href="/blog/rss.xml">RSS 2.0 feed</a> is also available.
          </div>
          <section class="rss-meta">
            <dl>
              <dt>Site</dt>
              <dd>
                <a>
                  <xsl:attribute name="href">
                    <xsl:value-of select="/atom:feed/atom:link[@rel='alternate']/@href"/>
                  </xsl:attribute>
                  <xsl:value-of select="/atom:feed/atom:link[@rel='alternate']/@href"/>
                </a>
              </dd>
              <dt>Updated</dt>
              <dd><xsl:value-of select="/atom:feed/atom:updated"/></dd>
              <dt>Posts</dt>
              <dd><xsl:value-of select="count(/atom:feed/atom:entry)"/></dd>
            </dl>
          </section>
          <xsl:for-each select="/atom:feed/atom:entry">
            <article class="rss-item">
              <h2 class="rss-item-title">
                <a href="{atom:link/@href}"><xsl:value-of select="atom:title"/></a>
              </h2>
              <div class="rss-item-meta">
                <span><xsl:value-of select="atom:published"/></span>
                <xsl:if test="atom:author/atom:name">
                  <span class="sep">&#183;</span>
                  <span><xsl:value-of select="atom:author/atom:name"/></span>
                </xsl:if>
                <xsl:if test="atom:category">
                  <span class="sep">&#183;</span>
                  <xsl:for-each select="atom:category">
                    <span class="rss-category"><xsl:value-of select="@term"/></span>
                  </xsl:for-each>
                </xsl:if>
              </div>
              <div class="rss-item-description">
                <xsl:value-of select="atom:summary" disable-output-escaping="yes"/>
              </div>
              <a class="rss-read-more" href="{atom:link/@href}">Read full article</a>
            </article>
          </xsl:for-each>
          <footer class="rss-footer">
            <p>
              <a href="/"><xsl:value-of select="/atom:feed/atom:title"/></a> &#183;
              Generated with <a href="https://www.mkdocs.org/" rel="noopener">MkDocs</a>,
              <a href="https://squidfunk.github.io/mkdocs-material/" rel="noopener">Material</a> and
              <a href="https://guts.github.io/mkdocs-rss-plugin/" rel="noopener">mkdocs-rss-plugin</a>
            </p>
            <p>
              <a href="/blog/rss.xml">RSS</a> &#183;
              <a href="/blog/atom.xml">Atom</a> &#183;
              Copyright &#169; 2026 PythonWoods &#8212; Apache-2.0
            </p>
          </footer>
        </main>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
