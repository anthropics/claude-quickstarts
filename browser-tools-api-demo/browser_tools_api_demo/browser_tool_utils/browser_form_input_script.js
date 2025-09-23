// Script for setting values in form elements by their reference IDs

(function(elementRef, inputValue) {
    try {
        // Get element from reference map
        let element = null;
        
        if (window.__claudeElementMap && window.__claudeElementMap[elementRef]) {
            const weakRef = window.__claudeElementMap[elementRef];
            element = weakRef.deref() || null;
            
            if (!element || !document.contains(element)) {
                // Element has been removed from DOM
                delete window.__claudeElementMap[elementRef];
                element = null;
            }
        }
        
        if (!element) {
            return {
                success: false,
                action: 'form_input',
                message: `No element found with reference: "${elementRef}". The element may have been removed from the page.`
            };
        }
        
        // Scroll element into view
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Handle different element types
        if (element instanceof HTMLSelectElement) {
            const previousValue = element.value;
            const options = Array.from(element.options);
            
            // Try to find option by value or text
            let optionFound = false;
            const valueStr = String(inputValue);
            
            for (let i = 0; i < options.length; i++) {
                if (options[i].value === valueStr || options[i].text === valueStr) {
                    element.selectedIndex = i;
                    optionFound = true;
                    break;
                }
            }
            
            if (!optionFound) {
                return {
                    success: false,
                    action: 'form_input',
                    message: `Option "${valueStr}" not found. Available options: ${options.map(o => `"${o.text}" (value: "${o.value}")`).join(', ')}`
                };
            }
            
            // Focus and dispatch events
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: 'select',
                previous_value: previousValue,
                new_value: element.value,
                message: `Selected option "${valueStr}" in dropdown`
            };
        } else if (element instanceof HTMLInputElement && element.type === 'checkbox') {
            const previousValue = element.checked;
            
            if (typeof inputValue !== 'boolean') {
                return {
                    success: false,
                    action: 'form_input',
                    message: 'Checkbox requires a boolean value (true/false)'
                };
            }
            
            element.checked = inputValue;
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: 'checkbox',
                previous_value: previousValue,
                new_value: element.checked,
                message: `Checkbox ${element.checked ? 'checked' : 'unchecked'}`
            };
        } else if (element instanceof HTMLInputElement && element.type === 'radio') {
            const previousValue = element.checked;
            const radioGroup = element.name;
            
            // For radio buttons, we always set to true (can't uncheck a radio by clicking)
            element.checked = true;
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: 'radio',
                previous_value: previousValue,
                new_value: element.checked,
                message: `Radio button selected${radioGroup ? ` in group "${radioGroup}"` : ''}`
            };
        } else if (element instanceof HTMLInputElement && 
                   (element.type === 'date' || element.type === 'time' || 
                    element.type === 'datetime-local' || element.type === 'month' || 
                    element.type === 'week')) {
            const previousValue = element.value;
            element.value = String(inputValue);
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: element.type,
                previous_value: previousValue,
                new_value: element.value,
                message: `Set ${element.type} to "${element.value}"`
            };
        } else if (element instanceof HTMLInputElement && element.type === 'range') {
            const previousValue = element.value;
            const numValue = Number(inputValue);
            
            if (isNaN(numValue)) {
                return {
                    success: false,
                    action: 'form_input',
                    message: 'Range input requires a numeric value'
                };
            }
            
            element.value = String(numValue);
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: 'range',
                previous_value: previousValue,
                new_value: element.value,
                message: `Set range to ${element.value} (min: ${element.min}, max: ${element.max})`
            };
        } else if (element instanceof HTMLInputElement && element.type === 'number') {
            const previousValue = element.value;
            const numValue = Number(inputValue);
            
            if (isNaN(numValue) && inputValue !== '') {
                return {
                    success: false,
                    action: 'form_input',
                    message: 'Number input requires a numeric value'
                };
            }
            
            element.value = String(inputValue);
            element.focus();
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: 'number',
                previous_value: previousValue,
                new_value: element.value,
                message: `Set number input to ${element.value}`
            };
        } else if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
            const previousValue = element.value;
            element.value = String(inputValue);
            element.focus();
            
            // Set cursor position to end
            element.setSelectionRange(element.value.length, element.value.length);
            
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            
            const elementType = element instanceof HTMLTextAreaElement ? 'textarea' : (element.type || 'text');
            
            return {
                success: true,
                action: 'form_input',
                ref: elementRef,
                element_type: elementType,
                previous_value: previousValue,
                new_value: element.value,
                message: `Set ${elementType} value to "${element.value}"`
            };
        } else {
            return {
                success: false,
                action: 'form_input',
                message: `Element type "${element.tagName}" is not a supported form input`
            };
        }
    } catch (error) {
        return {
            success: false,
            action: 'form_input',
            message: `Error setting form value: ${error.message || 'Unknown error'}`
        };
    }
})