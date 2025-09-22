// Script to extract raw text content from the page, prioritizing article content

(function() {
    try {
        // Priority order for finding article content
        const selectors = [
            'article',
            'main',
            '[class*="articleBody"]',
            '[class*="article-body"]',
            '[class*="post-content"]',
            '[class*="entry-content"]',
            '[class*="content-body"]',
            '[role="main"]',
            '.content',
            '#content'
        ];

        let contentElement = null;

        // Try each selector in order
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                // If multiple elements found, prefer the one with the most text content
                let bestElement = elements[0];
                let maxTextLength = 0;

                elements.forEach((el) => {
                    const textLength = el.textContent?.length || 0;
                    if (textLength > maxTextLength) {
                        maxTextLength = textLength;
                        bestElement = el;
                    }
                });

                contentElement = bestElement;
                break;
            }
        }

        if (!contentElement) {
            // Fallback to body if no specific content element found
            contentElement = document.body;
        }

        // Extract text content
        const textContent = contentElement.textContent || '';

        // Clean up the text: remove excessive whitespace, normalize line breaks
        const cleanedText = textContent
            .replace(/\s+/g, ' ')           // Replace multiple spaces with single space
            .replace(/\n{3,}/g, '\n\n')     // Replace 3+ newlines with double newline
            .trim();

        return {
            text: cleanedText,
            source: contentElement.tagName.toLowerCase(),
            title: document.title,
            url: window.location.href
        };
    } catch (error) {
        console.error('Error extracting page text:', error);
        throw new Error('Error extracting page text: ' + (error.message || 'Unknown error'));
    }
})