/*
 * Modifications Copyright (c) 2025 Anthropic, PBC
 * Modified from original Microsoft Playwright source
 * Original Microsoft Playwright source licensed under Apache License 2.0
 * See CHANGELOG.md for details
 */

// Content script that defines the accessibility tree generation function in the MAIN context

(function () {
  // Initialize global element map and ref counter if not already present
  if (!window.__claudeElementMap) {
    window.__claudeElementMap = {};
  }
  if (!window.__claudeRefCounter) {
    window.__claudeRefCounter = 0;
  }

  // Define the accessibility tree generation function on the window (in content script context)
  window.__generateAccessibilityTree = function (filterType) {
    try {
      var result = [];

      function getRole(element) {
        var role = element.getAttribute("role");
        if (role) return role;

        var tag = element.tagName.toLowerCase();
        var type = element.getAttribute("type");

        var roleMap = {
          a: "link",
          button: "button",
          input:
            type === "submit" || type === "button"
              ? "button"
              : type === "checkbox"
                ? "checkbox"
                : type === "radio"
                  ? "radio"
                  : type === "file"
                    ? "button"
                    : "textbox",
          select: "combobox",
          textarea: "textbox",
          h1: "heading",
          h2: "heading",
          h3: "heading",
          h4: "heading",
          h5: "heading",
          h6: "heading",
          img: "image",
          nav: "navigation",
          main: "main",
          header: "banner",
          footer: "contentinfo",
          section: "region",
          article: "article",
          aside: "complementary",
          form: "form",
          table: "table",
          ul: "list",
          ol: "list",
          li: "listitem",
          label: "label",
        };

        return roleMap[tag] || "generic";
      }

      function getCleanName(element) {
        var tag = element.tagName.toLowerCase();

        // For selects, get the selected option text
        if (tag === "select") {
          var selectElement = element;
          var selectedOption =
            selectElement.querySelector("option[selected]") ||
            selectElement.options[selectElement.selectedIndex];
          if (selectedOption && selectedOption.textContent) {
            return selectedOption.textContent.trim();
          }
        }

        // Priority order for getting meaningful names
        var ariaLabel = element.getAttribute("aria-label");
        if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

        var placeholder = element.getAttribute("placeholder");
        if (placeholder && placeholder.trim()) return placeholder.trim();

        var title = element.getAttribute("title");
        if (title && title.trim()) return title.trim();

        var alt = element.getAttribute("alt");
        if (alt && alt.trim()) return alt.trim();

        // For form labels
        if (element.id) {
          var label = document.querySelector('label[for="' + element.id + '"]');
          if (label && label.textContent && label.textContent.trim()) {
            return label.textContent.trim();
          }
        }

        // For inputs with values
        if (tag === "input") {
          var inputElement = element;
          var type = element.getAttribute("type") || "";
          var value = element.getAttribute("value");

          if (type === "submit" && value && value.trim()) {
            return value.trim();
          }

          if (
            inputElement.value &&
            inputElement.value.length < 50 &&
            inputElement.value.trim()
          ) {
            return inputElement.value.trim();
          }
        }

        // For buttons, links, and other interactive elements, get direct text
        if (["button", "a", "summary"].includes(tag)) {
          var directText = "";
          for (var i = 0; i < element.childNodes.length; i++) {
            var node = element.childNodes[i];
            if (node.nodeType === Node.TEXT_NODE) {
              directText += node.textContent;
            }
          }
          if (directText.trim()) return directText.trim();
        }

        // For headings, get text content but limit it
        if (tag.match(/^h[1-6]$/)) {
          var headingText = element.textContent;
          if (headingText && headingText.trim()) {
            return headingText.trim().substring(0, 100);
          }
        }

        // For images without alt, try to get surrounding context
        if (tag === "img") {
          var src = element.getAttribute("src");
          if (src) {
            var filename = src.split("/").pop()?.split("?")[0];
            return "Image: " + filename;
          }
        }

        // For generic elements, get direct text content (not including child elements)
        // This helps capture important text in spans, divs, etc.
        var directTextContent = "";
        for (var j = 0; j < element.childNodes.length; j++) {
          var childNode = element.childNodes[j];
          if (childNode.nodeType === Node.TEXT_NODE) {
            directTextContent += childNode.textContent;
          }
        }

        if (
          directTextContent &&
          directTextContent.trim() &&
          directTextContent.trim().length >= 3
        ) {
          // Only return if it's meaningful text (at least 3 characters)
          var trimmedText = directTextContent.trim();
          if (trimmedText.length > 50) {
            return trimmedText.substring(0, 50) + "...";
          }
          return trimmedText;
        }

        return "";
      }

      function isVisible(element) {
        var style = window.getComputedStyle(element);
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          style.opacity !== "0" &&
          element.offsetWidth > 0 &&
          element.offsetHeight > 0
        );
      }

      function isInteractive(element) {
        var tag = element.tagName.toLowerCase();
        var interactiveTags = [
          "a",
          "button",
          "input",
          "select",
          "textarea",
          "details",
          "summary",
        ];

        return (
          interactiveTags.includes(tag) ||
          element.getAttribute("onclick") !== null ||
          element.getAttribute("tabindex") !== null ||
          element.getAttribute("role") === "button" ||
          element.getAttribute("role") === "link" ||
          element.getAttribute("contenteditable") === "true"
        );
      }

      function isSemantic(element) {
        var tag = element.tagName.toLowerCase();
        var semanticTags = [
          "h1",
          "h2",
          "h3",
          "h4",
          "h5",
          "h6",
          "nav",
          "main",
          "header",
          "footer",
          "section",
          "article",
          "aside",
        ];
        return (
          semanticTags.includes(tag) || element.getAttribute("role") !== null
        );
      }

      function shouldIncludeElement(element, options) {
        var tag = element.tagName.toLowerCase();

        // Always skip these
        if (
          ["script", "style", "meta", "link", "title", "noscript"].includes(tag)
        )
          return false;
        if (element.getAttribute("aria-hidden") === "true") return false;

        // Always check visibility - this is now mandatory
        if (!isVisible(element)) return false;

        // Check viewport visibility for all elements (unless using 'all' filter for find tool)
        if (options.filter !== "all") {
          var rect = element.getBoundingClientRect();
          var inViewport =
            rect.top < window.innerHeight &&
            rect.bottom > 0 &&
            rect.left < window.innerWidth &&
            rect.right > 0;
          if (!inViewport) return false;
        }

        // Apply interactive filter if specified
        if (options.filter === "interactive") {
          return isInteractive(element);
        }

        // Default behavior when no filter is specified (all visible elements)
        // Always include interactive elements
        if (isInteractive(element)) return true;

        // Always include semantic elements (headings, nav, etc.)
        if (isSemantic(element)) return true;

        // Include elements with meaningful text content
        if (getCleanName(element).length > 0) return true;

        // For generic divs and spans, be more selective but still include text-containing ones
        var role = getRole(element);
        if (role === "generic" && (tag === "div" || tag === "span")) {
          var id = element.id || "";
          var className = element.className || "";
          var cleanName = getCleanName(element);

          // Include if it has meaningful text content (now that we extract text better)
          if (cleanName && cleanName.length >= 3) {
            return true;
          }

          // Only keep divs/spans that are clearly functional containers (not layout)
          var functionalKeywords = [
            "search",
            "dropdown",
            "menu",
            "modal",
            "dialog",
            "popup",
            "toolbar",
            "sidebar",
            "content",
            "text",
          ];
          var isFunctionalContainer = functionalKeywords.some(
            function (keyword) {
              return id.includes(keyword) || className.includes(keyword);
            },
          );

          if (isFunctionalContainer) {
            return true;
          }

          // Skip empty generic containers - they're just layout noise
          return false;
        }

        // Include other container elements that might have interactive children
        if (isContainerElement(element)) return true;

        return false;
      }

      function isContainerElement(element) {
        var role = element.getAttribute("role");
        var tag = element.tagName.toLowerCase();
        var className = element.className || "";
        var id = element.id || "";

        // These are containers that should be traversed deeper
        return (
          role === "search" ||
          role === "form" ||
          role === "group" ||
          role === "toolbar" ||
          role === "navigation" ||
          tag === "form" ||
          tag === "fieldset" ||
          tag === "nav" ||
          // Generic functional containers
          id.includes("search") ||
          className.includes("search") ||
          id.includes("form") ||
          className.includes("form") ||
          id.includes("menu") ||
          className.includes("menu") ||
          id.includes("nav") ||
          className.includes("nav")
        );
      }

      function processElement(element, depth, options) {
        if (depth > 15) return; // Generous depth limit for very complex pages
        if (!element || !element.tagName) return;

        var shouldInclude = shouldIncludeElement(element, options);
        var actuallyInclude = shouldInclude || depth === 0; // Always include root (body)

        if (actuallyInclude) {
          var role = getRole(element);
          var name = getCleanName(element);
          var ref = null;

          // Check if this element already has a ref in the global map
          for (var existingRef in window.__claudeElementMap) {
            var weakRef = window.__claudeElementMap[existingRef];
            var existingElement = weakRef.deref();
            if (existingElement === element) {
              ref = existingRef;
              break;
            }
          }

          // If not found, create a new ref
          if (!ref) {
            ref = "ref_" + ++window.__claudeRefCounter;
            window.__claudeElementMap[ref] = new WeakRef(element);
          }

          var indent = "  ".repeat(depth);
          var yaml = indent + "- " + role;

          if (name) {
            // Clean up the name - remove newlines, limit length
            name = name.replace(/\s+/g, " ").substring(0, 100);
            yaml += ' "' + name.replace(/"/g, '\\"') + '"';
          }

          yaml += " [ref=" + ref + "]";

          // Add useful attributes
          if (element.id) yaml += ' id="' + element.id + '"';
          if (element.getAttribute("href"))
            yaml += ' href="' + element.getAttribute("href") + '"';
          if (element.getAttribute("type"))
            yaml += ' type="' + element.getAttribute("type") + '"';
          if (element.getAttribute("placeholder"))
            yaml +=
              ' placeholder="' + element.getAttribute("placeholder") + '"';

          result.push(yaml);
        }

        // Always traverse children - we need to go deep to find interactive elements
        if (element.children && depth < 15) {
          for (var i = 0; i < element.children.length; i++) {
            processElement(
              element.children[i],
              actuallyInclude ? depth + 1 : depth,
              options,
            );
          }
        }
      }

      var options = {
        filter: filterType,
      };

      if (document.body) {
        processElement(document.body, 0, options);
      }

      // Clean up stale references (elements that have been garbage collected)
      for (var ref in window.__claudeElementMap) {
        var weakRef = window.__claudeElementMap[ref];
        if (!weakRef.deref()) {
          delete window.__claudeElementMap[ref];
        }
      }

      // Filter out empty generic elements
      var filteredResult = result.filter(function (line) {
        return !/^\s*- generic \[ref=ref_\d+\]$/.test(line);
      });

      return {
        pageContent: filteredResult.join("\n"),
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
        },
      };
    } catch (error) {
      console.error("Error in accessibility tree generation:", error);
      throw new Error(
        "Error generating accessibility tree: " +
          (error.message || "Unknown error"),
      );
    }
  };
})();