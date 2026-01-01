// Global variables
let variablesEditor, templateEditor;
let uploadedData = null;
let currentTemplateId = null;
let currentTemplateVersion = null;
let isEditMode = false;
let allTemplates = [];
let generatedConfigs = [];

// Notification system
function showNotification(title, message, type = 'info', buttons = null) {
    const modal = document.getElementById('notificationModal');
    const titleEl = document.getElementById('notificationTitle');
    const bodyEl = document.getElementById('notificationBody');
    const actionsEl = document.getElementById('notificationActions');
    const headerEl = document.getElementById('notificationHeader');

    // Set title
    titleEl.textContent = title;

    // Set message
    bodyEl.innerHTML = message;

    // Set header color based on type
    if (type === 'success') {
        headerEl.style.borderBottom = '1px solid #4CAF50';
        titleEl.style.color = '#4CAF50';
    } else if (type === 'error') {
        headerEl.style.borderBottom = '1px solid #f44336';
        titleEl.style.color = '#f44336';
    } else if (type === 'warning') {
        headerEl.style.borderBottom = '1px solid #FF9800';
        titleEl.style.color = '#FF9800';
    } else {
        headerEl.style.borderBottom = '1px solid #667eea';
        titleEl.style.color = '#667eea';
    }

    // Set buttons
    if (buttons) {
        actionsEl.innerHTML = buttons;
    } else {
        actionsEl.innerHTML = '<button class="button" onclick="closeNotification()">OK</button>';
    }

    modal.style.display = 'flex';
}

function closeNotification() {
    document.getElementById('notificationModal').style.display = 'none';
}

function confirm(message, onConfirm) {
    const buttons = `
        <button class="button button-secondary" onclick="closeNotification()">Cancel</button>
        <button class="button" style="background: #f44336;" onclick="closeNotification(); (${onConfirm})()">Confirm</button>
    `;
    showNotification('Confirm', message, 'warning', buttons);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeJinjaTester();
    initializeTemplateManager();
    setupDragAndDrop();
});

// ========== Tab Switching ==========
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');

    // Refresh editors if switching to jinja-tester
    if (tabName === 'jinja-tester' && variablesEditor && templateEditor) {
        setTimeout(() => {
            variablesEditor.refresh();
            templateEditor.refresh();
        }, 100);
    }

    // Load logs if switching to logs tab
    if (tabName === 'logs') {
        refreshLogs();
    }
}

// ========== Jinja Tester Tab ==========
function initializeJinjaTester() {
    // Initialize CodeMirror editors
    variablesEditor = CodeMirror.fromTextArea(document.getElementById('variables'), {
        mode: 'yaml',
        theme: 'monokai',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 2,
        tabSize: 2
    });

    templateEditor = CodeMirror.fromTextArea(document.getElementById('template'), {
        mode: 'jinja2',
        theme: 'monokai',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 2,
        tabSize: 2
    });

    const outputContainer = document.getElementById('output-container');
    const errorContainer = document.getElementById('template-error-container');

    let renderInProgress = false;
    let renderQueued = false;

    // HTML escape function
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Syntax highlighting for network configs (SecureCRT style)
    function highlightNetworkConfig(line) {
        const trimmed = line.trim();

        if (!trimmed) return escapeHtml(line);
        // Highlight switch separator lines (##### SWITCH_NAME #####)
        if (trimmed.match(/^#{3,}.*#{3,}$/)) {
            return `<div style="color: #00ff00; font-weight: bold; font-size: 1.1em; background: rgba(0, 255, 0, 0.1); padding: 8px; margin: 10px 0; border-left: 4px solid #00ff00; border-radius: 3px;">${escapeHtml(line)}</div>`;
        }
        if (trimmed === '!' || trimmed.startsWith('#')) {
            return `<span style="color: #808080;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^interface\s+/i)) {
            return `<span style="color: #00d7ff; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*description\s+/i)) {
            return `<span style="color: #00ff00;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*ip\s+(address|route)/i)) {
            const highlighted = escapeHtml(line).replace(/(\d+\.\d+\.\d+\.\d+)/g,
                '<span style="color: #ffff00;">$1</span>');
            return `<span style="color: #d4d4d4;">${highlighted}</span>`;
        }
        if (trimmed.match(/^\s*switchport/i)) {
            return `<span style="color: #ff00ff;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*(vlan|encapsulation)/i)) {
            const highlighted = escapeHtml(line).replace(/\b(\d+)\b/g,
                '<span style="color: #ffa500;">$1</span>');
            return `<span style="color: #ff8c00;">${highlighted}</span>`;
        }
        if (trimmed.match(/^\s*(channel-group|vpc|port-channel)/i)) {
            return `<span style="color: #87ceeb;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*spanning-tree/i)) {
            return `<span style="color: #90ee90;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*no\s+shutdown/i)) {
            return `<span style="color: #00ff00; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*shutdown/i)) {
            return `<span style="color: #ff0000; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*ptp/i)) {
            return `<span style="color: #dda0dd;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^(router|vrf)/i)) {
            return `<span style="color: #00ffff; font-weight: bold;">${escapeHtml(line)}</span>`;
        }

        return `<span style="color: #d4d4d4;">${escapeHtml(line)}</span>`;
    }

    async function renderTemplate() {
        if (renderInProgress) {
            renderQueued = true;
            return;
        }

        renderInProgress = true;
        const template = templateEditor.getValue();
        const variables = variablesEditor.getValue();

        errorContainer.innerHTML = '';
        templateEditor.getWrapperElement().classList.remove('error-highlight');

        if (!template && !variables) {
            outputContainer.textContent = '';
            renderInProgress = false;
            return;
        }

        try {
            const response = await fetch('/render', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({template, variables})
            });

            const data = await response.json();

            if (data.success) {
                const lines = data.output.trim().split('\n');
                const filteredLines = lines.filter(line => line.trim() !== '');
                const highlightedLines = filteredLines.map(line => highlightNetworkConfig(line));
                outputContainer.innerHTML = highlightedLines.join('\n');
            } else {
                outputContainer.textContent = '⚠️ Error:\n' + data.error;
                outputContainer.style.color = '#ff9800';
                errorContainer.innerHTML = '<div class="error-message">⚠️ ' + data.error + '</div>';
                templateEditor.getWrapperElement().classList.add('error-highlight');
                setTimeout(() => {
                    templateEditor.getWrapperElement().classList.remove('error-highlight');
                }, 300);
            }
        } catch (error) {
            outputContainer.textContent = '⚠️ Connection Error:\n' + error.message;
            outputContainer.style.color = '#ff9800';
        }

        renderInProgress = false;

        if (renderQueued) {
            renderQueued = false;
            setTimeout(renderTemplate, 0);
        }
    }

    variablesEditor.on('change', renderTemplate);
    templateEditor.on('change', renderTemplate);
    renderTemplate();
}

// ========== Config Generator Tab ==========
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('fileInput').files = files;
            handleFileUpload({target: {files}});
        }
    });
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload-excel', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // Sort data by switch name, then by eth_port
            const sortedData = sortDataByPortOrder(result.data);
            uploadedData = sortedData;

            const generateBtn = document.getElementById('generateBtn');
            if (generateBtn) generateBtn.disabled = false;
            document.getElementById('uploadArea').innerHTML = `
                <div class="upload-icon">✅</div>
                <div style="color: #4caf50; font-size: 1.1em; margin-bottom: 8px;">
                    File uploaded successfully: ${file.name}
                </div>
                <div style="color: #999; font-size: 0.9em;">
                    ${result.data.length} rows loaded
                </div>
                <div style="margin-top: 15px;">
                    <button class="button button-secondary" onclick="resetUploadArea()" style="font-size: 0.9em;">
                        🔄 RESET
                    </button>
                </div>
            `;

            // Display editable preview table
            displayEditablePreview(sortedData, result.columns);
        } else {
            alert('Error uploading file: ' + result.error);
        }
    } catch (error) {
        alert('Error uploading file: ' + error.message);
    }
}

function sortDataByPortOrder(data) {
    // Create a copy to avoid mutating the original
    const sortedData = [...data];

    // Helper function to extract numeric value from port string
    function extractPortNumber(portStr) {
        if (!portStr) return 0;
        // Handle formats like "Ethernet1/1", "eth1/1", "1/1", "1", etc.
        const match = String(portStr).match(/(\d+)\/(\d+)|(\d+)/);
        if (match) {
            if (match[1] && match[2]) {
                // Format: "1/1" - use slot*1000 + port for proper ordering
                return parseInt(match[1]) * 1000 + parseInt(match[2]);
            } else if (match[3]) {
                // Format: "1" - just the number
                return parseInt(match[3]);
            }
        }
        return 0;
    }

    sortedData.sort((a, b) => {
        // First sort by switch name
        const switchA = String(a.switch_name || a.hostname || '').toLowerCase();
        const switchB = String(b.switch_name || b.hostname || '').toLowerCase();

        if (switchA < switchB) return -1;
        if (switchA > switchB) return 1;

        // If switch names are equal, sort by eth_port
        const portA = extractPortNumber(a.eth_port || a.port || a.interface);
        const portB = extractPortNumber(b.eth_port || b.port || b.interface);

        return portA - portB;
    });

    return sortedData;
}

async function displayEditablePreview(data, columns) {
    const previewContainer = document.getElementById('dataPreview');
    if (!previewContainer) return;

    if (!data || data.length === 0) {
        previewContainer.innerHTML = '<div class="info-box">No data to preview</div>';
        return;
    }

    // Get all template names to validate against
    const templatesResponse = await fetch('/api/templates');
    const templates = await templatesResponse.json();
    const validTemplateNames = templates.map(t => t.name.toLowerCase());

    let tableHTML = '<div style="padding: 20px; padding-top: 0;"><table class="preview-table" style="width: 100%; border-collapse: collapse; background: #1e1e1e;">';

    // Header
    tableHTML += '<thead><tr style="position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.5);">';
    tableHTML += `<th style="padding: 10px; border: 1px solid #444; border-bottom: 2px solid #667eea; color: #999; font-weight: bold; text-align: center; width: 50px; background: #252526;">#</th>`;
    columns.forEach(col => {
        tableHTML += `<th style="padding: 10px; border: 1px solid #444; border-bottom: 2px solid #667eea; color: #fff; font-weight: bold; text-align: center; background: #2d2d30;">${escapeHtml(col)}</th>`;
    });
    tableHTML += '</tr></thead><tbody>';

    // Data rows
    data.forEach((row, rowIndex) => {
        // Check for errors in this row
        const template = row.template ? String(row.template).trim() : '';
        const switchName = row.switch_name ? String(row.switch_name).trim() : '';
        const switchPort = row.switch_port ? String(row.switch_port).trim() : '';

        const templateMissing = !template;
        const templateInvalid = template && !validTemplateNames.includes(template.toLowerCase());
        const switchNameMissing = !switchName;
        const switchPortMissing = !switchPort;

        const hasError = templateMissing || templateInvalid || switchNameMissing || switchPortMissing;
        const rowBgColor = hasError ? 'rgba(255, 0, 0, 0.15)' : 'transparent';

        tableHTML += `<tr style="background: ${rowBgColor};">`;
        // Line number column
        tableHTML += `<td style="padding: 8px; border: 1px solid #444; text-align: center; color: #999; background: #1a1a1a; font-family: 'Consolas', monospace; font-size: 0.85em;">${rowIndex + 1}</td>`;

        columns.forEach(col => {
            let value = row[col] !== undefined && row[col] !== null ? row[col] : '';

            // Clean switch_port value: remove "Port-" prefix and leading zeros
            if (col === 'switch_port' && value) {
                let cleanedValue = String(value).replace(/^Port-/i, '');
                // Remove leading zeros (e.g., "04" becomes "4")
                cleanedValue = cleanedValue.replace(/^0+(\d)/, '$1');
                // Update the actual data
                row[col] = cleanedValue;
                value = cleanedValue;
            }

            // Determine cell background color
            let cellBgColor = 'transparent';
            if (col === 'template' && (templateMissing || templateInvalid)) {
                cellBgColor = 'rgba(255, 0, 0, 0.3)';
            } else if (col === 'switch_name' && switchNameMissing) {
                cellBgColor = 'rgba(255, 0, 0, 0.3)';
            } else if (col === 'switch_port' && switchPortMissing) {
                cellBgColor = 'rgba(255, 0, 0, 0.3)';
            }

            tableHTML += `<td style="padding: 8px; border: 1px solid #444; text-align: center; background: ${cellBgColor};">
                <input type="text"
                       class="cell-input"
                       data-row="${rowIndex}"
                       data-col="${escapeHtml(col)}"
                       value="${escapeHtml(String(value))}"
                       style="width: 100%; background: transparent; border: none; color: #ccc; padding: 4px; font-family: 'Consolas', monospace; font-size: 0.9em; text-align: center;"
                       onchange="handleCellEdit(${rowIndex}, '${escapeHtml(col)}', this.value)">
            </td>`;
        });
        tableHTML += '</tr>';
    });

    tableHTML += '</tbody></table></div>';
    previewContainer.innerHTML = tableHTML;
}

async function handleCellEdit(rowIndex, column, value) {
    if (!uploadedData || !uploadedData[rowIndex]) return;

    // Update the data
    uploadedData[rowIndex][column] = value;
}

async function generateConfigs() {
    if (!uploadedData) {
        return;
    }

    try {
        const response = await fetch('/api/generate-configs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({excel_data: uploadedData})
        });

        const result = await response.json();

        if (result.success) {
            generatedConfigs = result.configs;
            displayConfigs(result.configs, result.success_row_count, result.error_row_count, result.skipped_row_count);
        } else {
            alert('Error generating configs: ' + result.error);
        }
    } catch (error) {
        alert('Error generating configs: ' + error.message);
    }
}

function displayConfigs(configs, successRowCount = 0, errorRowCount = 0, skippedRowCount = 0) {
    const resultsContainer = document.getElementById('configResults');

    if (configs.length === 0) {
        resultsContainer.innerHTML = '<div class="info-box">No configs generated</div>';
        return;
    }

    // Helper function for syntax highlighting
    function highlightNetworkConfig(line) {
        const trimmed = line.trim();

        if (!trimmed) return escapeHtml(line);
        // Highlight switch separator lines (##### SWITCH_NAME #####)
        if (trimmed.match(/^#{3,}.*#{3,}$/)) {
            return `<div style="color: #00ff00; font-weight: bold; font-size: 1.1em; background: rgba(0, 255, 0, 0.1); padding: 8px; margin: 10px 0; border-left: 4px solid #00ff00; border-radius: 3px;">${escapeHtml(line)}</div>`;
        }
        if (trimmed === '!' || trimmed.startsWith('#')) {
            return `<span style="color: #808080;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^interface\s+/i)) {
            return `<span style="color: #00d7ff; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*description\s+/i)) {
            return `<span style="color: #00ff00;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*ip\s+(address|route)/i)) {
            const highlighted = escapeHtml(line).replace(/(\d+\.\d+\.\d+\.\d+)/g,
                '<span style="color: #ffff00;">$1</span>');
            return `<span style="color: #d4d4d4;">${highlighted}</span>`;
        }
        if (trimmed.match(/^\s*switchport/i)) {
            return `<span style="color: #ff00ff;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*(vlan|encapsulation)/i)) {
            const highlighted = escapeHtml(line).replace(/\b(\d+)\b/g,
                '<span style="color: #ffa500;">$1</span>');
            return `<span style="color: #ff8c00;">${highlighted}</span>`;
        }
        if (trimmed.match(/^\s*(channel-group|vpc|port-channel)/i)) {
            return `<span style="color: #87ceeb;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*spanning-tree/i)) {
            return `<span style="color: #90ee90;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*no\s+shutdown/i)) {
            return `<span style="color: #00ff00; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*shutdown/i)) {
            return `<span style="color: #ff0000; font-weight: bold;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^\s*ptp/i)) {
            return `<span style="color: #dda0dd;">${escapeHtml(line)}</span>`;
        }
        if (trimmed.match(/^(router|vrf)/i)) {
            return `<span style="color: #00ffff; font-weight: bold;">${escapeHtml(line)}</span>`;
        }

        return `<span style="color: #d4d4d4;">${escapeHtml(line)}</span>`;
    }

    // Collect all successful configs into a single output
    const successConfigs = configs.filter(c => c.success);
    const errorConfigs = configs.filter(c => !c.success);

    if (successConfigs.length === 0) {
        // Only errors
        resultsContainer.innerHTML = `
            <div class="info-box" style="background: #3d1f1f; border-color: #f44336;">
                <div style="color: #f44336; font-weight: bold; margin-bottom: 10px;">⚠️ Configuration Generation Errors</div>
                ${errorConfigs.map(config => `
                    <div style="margin-bottom: 10px; padding: 8px; background: #2d1515; border-radius: 4px;">
                        <div style="color: #ff8080; font-size: 0.9em; margin-bottom: 4px;">
                            ${config.row.host_type || 'N/A'}/${config.row.port_type || 'N/A'}/${config.row.switch_os || 'N/A'}
                        </div>
                        <div style="color: #ffcccc; font-size: 0.85em;">${config.error}</div>
                    </div>
                `).join('')}
            </div>
        `;
        return;
    }

    // Combine all configs into one output (just the config content, no separators)
    const combinedConfig = successConfigs.map(config => config.config).join('\n');

    // Clean up excessive blank lines for clipboard copy - replace 2 or more blank lines with single blank line
    const cleanedConfig = combinedConfig.replace(/\n\s*\n\s*\n+/g, '\n\n').trim();

    // Apply syntax highlighting - keep single blank lines but remove excessive ones
    const lines = cleanedConfig.split('\n');
    const highlightedLines = lines.map(line => highlightNetworkConfig(line));

    // Calculate total skipped (errors + skipped validation)
    const totalSkipped = errorRowCount + skippedRowCount;

    // Display in a single textbox-style output
    resultsContainer.innerHTML = `
        <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
            <div style="color: #4CAF50; font-size: 0.95em;">
                ✓ Prepared configs for ${successRowCount} line${successRowCount !== 1 ? 's' : ''}${totalSkipped > 0 ? `, skipped ${totalSkipped} line${totalSkipped !== 1 ? 's' : ''}` : ''}
            </div>
            <button class="button button-secondary" onclick="copyConfigToClipboard()">Copy</button>
        </div>
        <div class="config-output">
            ${highlightedLines.join('\n')}
        </div>
    `;

    // Store the cleaned config for copying
    window.currentCombinedConfig = cleanedConfig;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyConfigToClipboard() {
    if (!window.currentCombinedConfig) {
        alert('No config to copy');
        return;
    }

    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(window.currentCombinedConfig).then(() => {
            alert('Configuration copied to clipboard!');
        }).catch(err => {
            console.error('Clipboard API failed:', err);
            // Fallback to old method
            fallbackCopyToClipboard(window.currentCombinedConfig);
        });
    } else {
        // Use fallback method
        fallbackCopyToClipboard(window.currentCombinedConfig);
    }
}

function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        alert('Configuration copied to clipboard!');
    } catch (err) {
        console.error('Fallback copy failed:', err);
        alert('Failed to copy to clipboard. Please copy manually.');
    }
    document.body.removeChild(textArea);
}

function resetUploadArea() {
    // Simply reload the page to reset everything
    window.location.reload();
}

function downloadConfig() {
    if (!window.currentCombinedConfig) {
        alert('No config to download');
        return;
    }

    const blob = new Blob([window.currentCombinedConfig], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'generated_config.txt';
    a.click();
    URL.revokeObjectURL(url);
}

// ========== Template Manager Tab ==========
async function initializeTemplateManager() {
    await loadMetadata();
    await loadTemplates();
}

async function loadMetadata() {
    // Metadata is now managed through modals only, no filter dropdowns to populate
}

async function loadTemplates() {
    try {
        const response = await fetch('/api/templates');
        allTemplates = await response.json();
        displayTemplates(allTemplates);
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

function searchTemplates() {
    const searchTerm = document.getElementById('templateSearch').value.toLowerCase();

    if (!searchTerm) {
        displayTemplates(allTemplates);
        return;
    }

    const filtered = allTemplates.filter(t => {
        return t.name.toLowerCase().includes(searchTerm) ||
               t.host_type.toLowerCase().includes(searchTerm) ||
               t.port_type.toLowerCase().includes(searchTerm) ||
               t.switch_os.toLowerCase().includes(searchTerm) ||
               (t.description && t.description.toLowerCase().includes(searchTerm));
    });

    displayTemplates(filtered);
}

function displayTemplates(templates) {
    const listContainer = document.getElementById('templateList');

    if (templates.length === 0) {
        listContainer.innerHTML = '<div style="padding: 15px; color: #999; text-align: center;">No templates found</div>';
        return;
    }

    listContainer.innerHTML = templates.map(t => `
        <div class="template-item" onclick="selectTemplate(${t.id}, event)">
            <div class="template-item-title">${t.name}</div>
            <div class="template-item-meta">
                ${t.host_type} | ${t.port_type} | ${t.switch_os}
            </div>
        </div>
    `).join('');
}

async function selectTemplate(templateId, event) {
    try {
        const response = await fetch(`/api/templates/${templateId}`);
        const template = await response.json();

        currentTemplateId = templateId;
        currentTemplateVersion = template.active_version || 1;
        isEditMode = false;

        document.querySelectorAll('.template-item').forEach(item => {
            item.classList.remove('selected');
        });
        if (event && event.target) {
            event.target.closest('.template-item').classList.add('selected');
        }

        await showTemplateForm(template);
    } catch (error) {
        console.error('Error loading template:', error);
    }
}

async function showTemplateForm(template = null) {
    const formContainer = document.getElementById('templateForm');
    const actionsContainer = document.getElementById('formActions');

    if (!template) {
        // Creating new template
        const hostTypes = await fetch('/api/host-types').then(r => r.json());
        const portTypes = await fetch('/api/port-types').then(r => r.json());

        formContainer.innerHTML = `
            <div class="form-group">
                <label class="form-label">Template Name *</label>
                <input type="text" class="form-input" id="templateName" required>
            </div>
            <div class="form-group">
                <label class="form-label">Host Type *</label>
                <select class="form-select" id="templateHostType" required>
                    ${hostTypes.map(ht => `<option value="${ht}">${ht}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Port Type *</label>
                <select class="form-select" id="templatePortType" onchange="loadOSOptions()" required>
                    ${portTypes.map(pt => `<option value="${pt}">${pt}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Switch OS *</label>
                <select class="form-select" id="templateSwitchOS" required></select>
            </div>
            <div class="form-group">
                <label class="form-label">Version Description (optional)</label>
                <input type="text" class="form-input" id="versionDescription" placeholder="Describe this version...">
            </div>
            <div class="form-group">
                <label class="form-label">Template Content (Jinja2) *</label>
                <textarea class="form-textarea" id="templateContent" rows="20" required></textarea>
            </div>
        `;

        actionsContainer.innerHTML = `
            <button class="button button-secondary" onclick="cancelEdit()">Cancel</button>
            <button class="button" onclick="saveTemplate()">Save Template</button>
        `;
        actionsContainer.style.display = 'flex';
        await loadOSOptions();
        return;
    }

    // Load versions for existing template
    const versions = await fetch(`/api/templates/${template.id}/versions`).then(r => r.json());
    const currentVersion = await fetch(`/api/templates/${template.id}/versions/${currentTemplateVersion}`).then(r => r.json());

    const hostTypes = await fetch('/api/host-types').then(r => r.json());
    const portTypes = await fetch('/api/port-types').then(r => r.json());
    const osTypes = await fetch('/api/switch-os-types').then(r => r.json());

    const readonly = !isEditMode;
    const readonlyAttr = readonly ? 'disabled' : '';

    formContainer.innerHTML = `
        <div class="form-group">
            <label class="form-label">Template Name *</label>
            <input type="text" class="form-input" id="templateName" value="${escapeHtml(template.name)}" ${readonlyAttr} required>
        </div>
        <div class="form-group">
            <label class="form-label">Host Type *</label>
            <select class="form-select" id="templateHostType" ${readonlyAttr} required>
                ${hostTypes.map(ht => `<option value="${ht}" ${template.host_type === ht ? 'selected' : ''}>${ht}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Port Type *</label>
            <select class="form-select" id="templatePortType" ${readonlyAttr} required>
                ${portTypes.map(pt => `<option value="${pt}" ${template.port_type === pt ? 'selected' : ''}>${pt}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Switch OS *</label>
            <select class="form-select" id="templateSwitchOS" ${readonlyAttr} required>
                ${osTypes.map(os => `<option value="${os}" ${template.switch_os === os ? 'selected' : ''}>${os}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Version</label>
            <select class="form-select" id="versionSelect" onchange="loadVersion()" style="margin-bottom: 10px;">
                ${versions.map(v => `<option value="${v.version}" ${v.version === currentTemplateVersion ? 'selected' : ''}>${escapeHtml(v.version_name)}${v.is_active ? ' (Active)' : ''}</option>`).join('')}
                <option value="new">+ Create New Version</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Version Name</label>
            <input type="text" class="form-input" id="versionName" value="${escapeHtml(currentVersion.version_name || '')}" ${readonlyAttr}>
        </div>
        <div class="form-group">
            <label class="form-label">Version Description</label>
            <input type="text" class="form-input" id="versionDescription" value="${escapeHtml(currentVersion.version_description || '')}" ${readonlyAttr}>
        </div>
        <div class="form-group">
            <label class="form-label">Template Content (Jinja2) *</label>
            <textarea class="form-textarea" id="templateContent" rows="20" ${readonlyAttr} required>${escapeHtml(currentVersion.template_content || '')}</textarea>
        </div>
    `;

    // Update action buttons based on mode
    if (readonly) {
        actionsContainer.innerHTML = `
            <button class="button button-secondary" onclick="cancelEdit()">Cancel</button>
            <button class="button" style="background: #c62828;" onclick="deleteTemplate()">Delete Template</button>
            <button class="button" style="background: #f44336;" onclick="deleteVersion()">Delete Version</button>
            <button class="button" onclick="enableEditMode()" style="background: #FF9800;">Edit</button>
            <button class="button" onclick="setActiveVersion()" style="background: #4CAF50;">Active</button>
        `;
    } else {
        actionsContainer.innerHTML = `
            <button class="button button-secondary" onclick="cancelEdit()">Cancel</button>
            <button class="button" style="background: #c62828;" onclick="deleteTemplate()">Delete Template</button>
            <button class="button" onclick="saveTemplate()">Save</button>
        `;
    }
    actionsContainer.style.display = 'flex';
}

async function loadOSOptions() {
    const osSelect = document.getElementById('templateSwitchOS');
    const currentOS = osSelect.value;

    const osTypes = await fetch('/api/switch-os-types').then(r => r.json());

    osSelect.innerHTML = osTypes.map(osType => `
        <option value="${osType}" ${osType === currentOS ? 'selected' : ''}>${osType}</option>
    `).join('');
}

function createNewTemplate() {
    currentTemplateId = null;
    document.querySelectorAll('.template-item').forEach(item => {
        item.classList.remove('selected');
    });
    showTemplateForm();
}

async function saveTemplate() {
    const name = document.getElementById('templateName').value;
    const hostType = document.getElementById('templateHostType').value;
    const portType = document.getElementById('templatePortType').value;
    const switchOS = document.getElementById('templateSwitchOS').value;
    const content = document.getElementById('templateContent').value;
    const versionDescriptionEl = document.getElementById('versionDescription');
    const versionDescription = versionDescriptionEl ? versionDescriptionEl.value : '';
    const versionName = document.getElementById('versionName')?.value || '';

    if (!name || !hostType || !portType || !switchOS || !content) {
        showNotification('Missing Fields', 'Please fill in all required fields', 'error');
        return;
    }

    try {
        if (!currentTemplateId) {
            // Creating new template
            const response = await fetch('/api/templates', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name,
                    host_type: hostType,
                    port_type: portType,
                    switch_os: switchOS,
                    template_content: content,
                    version_description: versionDescription
                })
            });

            const result = await response.json();

            if (result.success) {
                showNotification('Success', 'Template created successfully!', 'success');
                await loadTemplates();
                currentTemplateId = result.template_id;
                currentTemplateVersion = 1;
                isEditMode = false;
                const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
                await showTemplateForm(template);
            } else {
                showNotification('Error', 'Error creating template: ' + result.error, 'error');
            }
        } else if (isEditMode) {
            // Update existing version
            const response = await fetch(`/api/templates/${currentTemplateId}/versions/${currentTemplateVersion}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    version_name: versionName,
                    version_description: versionDescription,
                    template_content: content
                })
            });

            const result = await response.json();

            if (result.success) {
                // Also update template metadata
                await fetch(`/api/templates/${currentTemplateId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name,
                        host_type: hostType,
                        port_type: portType,
                        switch_os: switchOS
                    })
                });

                showNotification('Success', 'Template saved successfully!', 'success');
                isEditMode = false;
                await loadTemplates();
                const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
                await showTemplateForm(template);
            } else {
                showNotification('Error', 'Error saving template: ' + result.error, 'error');
            }
        }
    } catch (error) {
        showNotification('Error', 'Error saving template: ' + error.message, 'error');
    }
}

async function deleteTemplate() {
    if (!currentTemplateId) return;

    const buttons = `
        <button class="button button-secondary" onclick="closeNotification()">Cancel</button>
        <button class="button" style="background: #f44336;" onclick="closeNotification(); confirmDeleteTemplate()">Delete</button>
    `;
    showNotification('Confirm Delete', 'Are you sure you want to delete this template and all its versions?', 'warning', buttons);
}

async function confirmDeleteTemplate() {
    try {
        const response = await fetch(`/api/templates/${currentTemplateId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'Template deleted successfully!', 'success');
            currentTemplateId = null;
            await loadTemplates();
            cancelEdit();
        } else {
            showNotification('Error', 'Error deleting template: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error', 'Error deleting template: ' + error.message, 'error');
    }
}

function cancelEdit() {
    currentTemplateId = null;
    currentTemplateVersion = null;
    isEditMode = false;
    document.getElementById('templateForm').innerHTML = `
        <div class="info-box">
            Select a template from the list or create a new one to start editing.
        </div>
    `;
    document.getElementById('formActions').style.display = 'none';
    document.querySelectorAll('.template-item').forEach(item => {
        item.classList.remove('selected');
    });
}

async function loadVersion() {
    const versionSelect = document.getElementById('versionSelect');
    const selectedValue = versionSelect.value;

    if (selectedValue === 'new') {
        // Show input modal for new version
        showVersionInputModal();
    } else {
        // Load selected version
        currentTemplateVersion = parseInt(selectedValue);
        isEditMode = false;
        const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
        await showTemplateForm(template);
    }
}

function showVersionInputModal() {
    const inputForm = `
        <div style="margin-bottom: 15px;">
            <label class="form-label">Version Name *</label>
            <input type="text" id="newVersionName" class="form-input" placeholder="e.g., v2.0" style="width: 100%;">
        </div>
        <div style="margin-bottom: 15px;">
            <label class="form-label">Version Description (optional)</label>
            <textarea id="newVersionDescription" class="form-textarea" rows="3" placeholder="Describe what changed in this version..." style="width: 100%;"></textarea>
        </div>
    `;

    const buttons = `
        <button class="button button-secondary" onclick="closeNotification(); document.getElementById('versionSelect').value = ${currentTemplateVersion}">Cancel</button>
        <button class="button" style="background: #4CAF50;" onclick="createNewVersionFromModal()">Create Version</button>
    `;

    showNotification('Create New Version', inputForm, 'info', buttons);

    // Focus on input after modal opens
    setTimeout(() => {
        const input = document.getElementById('newVersionName');
        if (input) input.focus();
    }, 100);
}

async function createNewVersionFromModal() {
    const versionName = document.getElementById('newVersionName').value.trim();
    const versionDescription = document.getElementById('newVersionDescription').value.trim();
    const versionSelect = document.getElementById('versionSelect');

    if (!versionName) {
        showNotification('Missing Field', 'Please enter a version name', 'error');
        return;
    }

    closeNotification();

    const content = document.getElementById('templateContent').value;

    try {
        const response = await fetch(`/api/templates/${currentTemplateId}/versions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                version_name: versionName,
                version_description: versionDescription,
                template_content: content
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'New version created successfully!', 'success');
            currentTemplateVersion = result.version;
            isEditMode = false;
            const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
            await showTemplateForm(template);
        } else {
            showNotification('Error', 'Error creating version: ' + result.error, 'error');
            versionSelect.value = currentTemplateVersion;
        }
    } catch (error) {
        showNotification('Error', 'Error creating version: ' + error.message, 'error');
        versionSelect.value = currentTemplateVersion;
    }
}

async function enableEditMode() {
    isEditMode = true;
    const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
    await showTemplateForm(template);
}

async function setActiveVersion() {
    if (!currentTemplateId || !currentTemplateVersion) return;

    const buttons = `
        <button class="button button-secondary" onclick="closeNotification()">Cancel</button>
        <button class="button" style="background: #4CAF50;" onclick="closeNotification(); confirmSetActiveVersion()">Set Active</button>
    `;
    showNotification('Confirm', `Set version ${currentTemplateVersion} as the active version?`, 'info', buttons);
}

async function confirmSetActiveVersion() {
    try {
        const response = await fetch(`/api/templates/${currentTemplateId}/active-version/${currentTemplateVersion}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'Active version updated successfully!', 'success');
            await loadTemplates();
            const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
            await showTemplateForm(template);
        } else {
            showNotification('Error', 'Error setting active version: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error', 'Error setting active version: ' + error.message, 'error');
    }
}

async function deleteVersion() {
    if (!currentTemplateId || !currentTemplateVersion) return;

    const buttons = `
        <button class="button button-secondary" onclick="closeNotification()">Cancel</button>
        <button class="button" style="background: #f44336;" onclick="closeNotification(); confirmDeleteVersion()">Delete</button>
    `;
    showNotification('Confirm Delete', `Are you sure you want to delete version ${currentTemplateVersion}?`, 'warning', buttons);
}

async function confirmDeleteVersion() {
    try {
        const response = await fetch(`/api/templates/${currentTemplateId}/versions/${currentTemplateVersion}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'Version deleted successfully!', 'success');
            await loadTemplates();
            const template = await fetch(`/api/templates/${currentTemplateId}`).then(r => r.json());
            currentTemplateVersion = template.active_version || 1;
            isEditMode = false;
            await showTemplateForm(template);
        } else {
            showNotification('Error', 'Error deleting version: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error', 'Error deleting version: ' + error.message, 'error');
    }
}

// ========== Metadata Management ==========

// Export Database
async function exportDatabase() {
    try {
        const response = await fetch('/api/export-database');
        const blob = await response.blob();

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `templates_backup_${new Date().toISOString().split('T')[0]}.db`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error exporting database:', error);
        alert('Error exporting database: ' + error.message);
    }
}

// Import/Restore Database
async function importDatabase(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Store file in temporary variable for later use
    window.pendingDatabaseFile = file;
    window.pendingDatabaseInput = event.target;

    const buttons = `
        <button class="button button-secondary" onclick="closeNotification(); cancelDatabaseRestore()">Cancel</button>
        <button class="button" style="background: #f44336;" onclick="closeNotification(); confirmDatabaseRestore()">Restore</button>
    `;
    showNotification(
        'Confirm Restore',
        '<strong>Warning:</strong> This will replace your current database.<br><br>All existing templates and settings will be lost.<br><br>Continue?',
        'warning',
        buttons
    );
}

function cancelDatabaseRestore() {
    if (window.pendingDatabaseInput) {
        window.pendingDatabaseInput.value = '';
    }
    window.pendingDatabaseFile = null;
    window.pendingDatabaseInput = null;
}

async function confirmDatabaseRestore() {
    const file = window.pendingDatabaseFile;
    const inputElement = window.pendingDatabaseInput;

    if (!file) return;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/import-database', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'Database restored successfully! Reloading page...', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showNotification('Error', 'Error restoring database: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error importing database:', error);
        showNotification('Error', 'Error importing database: ' + error.message, 'error');
    } finally {
        if (inputElement) {
            inputElement.value = '';
        }
        window.pendingDatabaseFile = null;
        window.pendingDatabaseInput = null;
    }
}

// Host Type Manager
async function showHostTypeManager() {
    document.getElementById('hostTypeModal').style.display = 'flex';
    await loadHostTypesList();
}

function closeHostTypeManager() {
    document.getElementById('hostTypeModal').style.display = 'none';
}

async function loadHostTypesList() {
    try {
        const response = await fetch('/api/host-types');
        const hostTypes = await response.json();

        document.getElementById('hostTypesList').innerHTML = hostTypes.map(ht => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #2d2d30; border-radius: 4px; margin-bottom: 8px;">
                <span style="color: #ccc;">${ht}</span>
                <button onclick="deleteHostType('${ht.replace(/'/g, "\\'")}')" style="background: #f44336; border: none; color: white; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
            </div>
        `).join('') || '<div style="color: #999; padding: 20px; text-align: center;">No host types</div>';
    } catch (error) {
        console.error('Error loading host types:', error);
        alert('Error loading host types: ' + error.message);
    }
}

async function addHostType() {
    const input = document.getElementById('newHostType');
    const name = input.value.trim();

    if (!name) {
        alert('Please enter a host type name');
        return;
    }

    try {
        const response = await fetch('/api/host-types', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            input.value = '';
            await loadHostTypesList();
            await loadMetadata();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteHostType(name) {
    if (!confirm(`Delete "${name}"? This may affect existing templates.`)) return;

    try {
        const response = await fetch('/api/host-types/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            await loadHostTypesList();
            await loadMetadata();
            await loadTemplates();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Vendor Manager
async function showVendorManager() {
    document.getElementById('vendorModal').style.display = 'flex';
    await loadVendorsList();
}

function closeVendorManager() {
    document.getElementById('vendorModal').style.display = 'none';
}

async function loadVendorsList() {
    try {
        const response = await fetch('/api/port-types');
        const vendors = await response.json();

        document.getElementById('vendorsList').innerHTML = vendors.map(v => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #2d2d30; border-radius: 4px; margin-bottom: 8px;">
                <span style="color: #ccc;">${v}</span>
                <button onclick="deleteVendor('${v.replace(/'/g, "\\'")}')" style="background: #f44336; border: none; color: white; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
            </div>
        `).join('') || '<div style="color: #999; padding: 20px; text-align: center;">No vendors</div>';
    } catch (error) {
        console.error('Error loading vendors:', error);
        alert('Error loading vendors: ' + error.message);
    }
}

async function addVendor() {
    const input = document.getElementById('newVendor');
    const name = input.value.trim();

    if (!name) {
        alert('Please enter a vendor name');
        return;
    }

    try {
        const response = await fetch('/api/port-types', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            input.value = '';
            await loadVendorsList();
            await loadMetadata();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteVendor(name) {
    if (!confirm(`Delete "${name}"? This may affect existing templates.`)) return;

    try {
        const response = await fetch('/api/port-types/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            await loadVendorsList();
            await loadMetadata();
            await loadTemplates();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// OS Manager
async function showOSManager() {
    document.getElementById('osModal').style.display = 'flex';
    await loadOSList();
}

function closeOSManager() {
    document.getElementById('osModal').style.display = 'none';
}

async function loadOSList() {
    try {
        const response = await fetch('/api/switch-os-types');
        const osTypes = await response.json();

        document.getElementById('osList').innerHTML = osTypes.map(switch_os => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #2d2d30; border-radius: 4px; margin-bottom: 8px;">
                <span style="color: #ccc;">${switch_os}</span>
                <button onclick="deleteOS('${switch_os.replace(/'/g, "\\'")}')" style="background: #f44336; border: none; color: white; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
            </div>
        `).join('') || '<div style="color: #999; padding: 20px; text-align: center;">No OS types</div>';
    } catch (error) {
        console.error('Error loading OS types:', error);
        alert('Error loading OS types: ' + error.message);
    }
}

async function addOS() {
    const input = document.getElementById('newOS');
    const name = input.value.trim();

    if (!name) {
        alert('Please enter an OS name');
        return;
    }

    try {
        const response = await fetch('/api/switch-os-types', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            input.value = '';
            await loadOSList();
            await loadMetadata();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteOS(name) {
    if (!confirm(`Delete "${name}"? This may affect existing templates.`)) return;

    try {
        const response = await fetch('/api/switch-os-types/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });

        const result = await response.json();

        if (result.success) {
            await loadOSList();
            await loadMetadata();
            await loadTemplates();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}


// Resizable panels functionality
document.addEventListener("DOMContentLoaded", () => {
    const resizeHandle = document.getElementById("resizeHandle");
    const leftPanel = document.querySelector(".left-panel");
    const splitView = document.querySelector(".split-view");

    if (resizeHandle && leftPanel && splitView) {
        let isResizing = false;

        resizeHandle.addEventListener("mousedown", (e) => {
            isResizing = true;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        });

        document.addEventListener("mousemove", (e) => {
            if (!isResizing) return;

            const containerRect = splitView.getBoundingClientRect();
            const newWidth = e.clientX - containerRect.left;
            const percentage = (newWidth / containerRect.width) * 100;

            // Keep between 20% and 80%
            if (percentage >= 20 && percentage <= 80) {
                leftPanel.style.flex = `0 0 ${percentage}%`;
            }
        });

        document.addEventListener("mouseup", () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
            }
        });
    }

    // Config Generator resizer
    const resizer = document.getElementById("resizer");
    const leftPanelConfig = document.getElementById("leftPanel");
    const configGenerator = document.getElementById("config-generator");

    if (resizer && leftPanelConfig && configGenerator) {
        let isResizingConfig = false;

        resizer.addEventListener("mousedown", (e) => {
            isResizingConfig = true;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
            e.preventDefault();
        });

        document.addEventListener("mousemove", (e) => {
            if (!isResizingConfig) return;

            const containerRect = configGenerator.getBoundingClientRect();
            const newWidth = e.clientX - containerRect.left;
            const percentage = (newWidth / containerRect.width) * 100;

            // Keep between 20% and 80%
            if (percentage >= 20 && percentage <= 80) {
                leftPanelConfig.style.width = `${percentage}%`;
            }
        });

        document.addEventListener("mouseup", () => {
            if (isResizingConfig) {
                isResizingConfig = false;
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
            }
        });
    }
});

// ========== Logs Tab ==========
let allLogs = [];

async function refreshLogs() {
    try {
        const response = await fetch('/api/logs');
        const result = await response.json();

        if (result.success) {
            allLogs = result.logs;
            filterLogs();
        } else {
            document.getElementById('logsContainer').innerHTML = '<div style="color: #f44336;">Error loading logs</div>';
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
        document.getElementById('logsContainer').innerHTML = `<div style="color: #f44336;">Error: ${error.message}</div>`;
    }
}

function filterLogs() {
    if (!allLogs || allLogs.length === 0) {
        refreshLogs();
        return;
    }

    const searchText = document.getElementById('logSearch').value.toLowerCase();
    const levelFilter = document.getElementById('logLevel').value;
    const startTime = document.getElementById('logStartTime').value;
    const endTime = document.getElementById('logEndTime').value;

    let filtered = allLogs;

    // Filter by log level
    if (levelFilter !== 'all') {
        filtered = filtered.filter(log => log.level === levelFilter);
    }

    // Filter by time range (custom date/time pickers)
    if (startTime || endTime) {
        filtered = filtered.filter(log => {
            // Parse log timestamp: "2026-01-01 20:58:21" (UTC)
            const logTime = new Date(log.timestamp.replace(' ', 'T') + 'Z');

            if (startTime) {
                const start = new Date(startTime);
                if (logTime < start) return false;
            }

            if (endTime) {
                const end = new Date(endTime);
                if (logTime > end) return false;
            }

            return true;
        });
    }

    // Filter by search text
    if (searchText) {
        filtered = filtered.filter(log =>
            log.message.toLowerCase().includes(searchText) ||
            log.module.toLowerCase().includes(searchText) ||
            log.level.toLowerCase().includes(searchText)
        );
    }

    displayLogs(filtered);
}

function updateDateDisplay(inputId, displayId) {
    const input = document.getElementById(inputId);
    const display = document.getElementById(displayId);

    if (input.value) {
        // Convert to readable format: "2026-01-01T20:58" -> "01/01/2026 08:58 PM"
        const date = new Date(input.value);
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const year = date.getFullYear();
        let hours = date.getHours();
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12 || 12;
        display.textContent = `${month}/${day}/${year} ${hours}:${minutes} ${ampm}`;
        display.style.color = '#ccc';
    } else {
        display.textContent = 'Select date/time...';
        display.style.color = '#666';
    }
}

function clearTimeFilters() {
    document.getElementById('logStartTime').value = '';
    document.getElementById('logEndTime').value = '';
    document.getElementById('logStartDisplay').textContent = 'Select date/time...';
    document.getElementById('logStartDisplay').style.color = '#666';
    document.getElementById('logEndDisplay').textContent = 'Select date/time...';
    document.getElementById('logEndDisplay').style.color = '#666';
    filterLogs();
}

function displayLogs(logs) {
    const container = document.getElementById('logsContainer');

    if (logs.length === 0) {
        container.innerHTML = '<div style="color: #999; text-align: center; padding: 20px;">No logs available</div>';
        return;
    }

    let html = '';
    // Create a reversed copy instead of modifying the original
    [...logs].reverse().forEach(log => {
        let levelColor = '#999';

        switch(log.level) {
            case 'ERROR':
                levelColor = '#f44336';
                break;
            case 'WARNING':
                levelColor = '#FF9800';
                break;
            case 'INFO':
                levelColor = '#4CAF50';
                break;
            case 'DEBUG':
                levelColor = '#2196F3';
                break;
        }

        // Format timestamp in US format with UTC indicator
        // Input: "2026-01-01 20:58:21" -> Output: "01/01/2026 08:58:21 PM UTC"
        const formatTimestamp = (timestamp) => {
            const date = new Date(timestamp.replace(' ', 'T') + 'Z');
            const month = String(date.getUTCMonth() + 1).padStart(2, '0');
            const day = String(date.getUTCDate()).padStart(2, '0');
            const year = date.getUTCFullYear();
            let hours = date.getUTCHours();
            const minutes = String(date.getUTCMinutes()).padStart(2, '0');
            const seconds = String(date.getUTCSeconds()).padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12 || 12;
            return `${month}/${day}/${year} ${hours}:${minutes}:${seconds} ${ampm} UTC`;
        };

        // Single line format: [timestamp] LEVEL: message (module:line)
        html += `<div style="color: #ccc; font-family: 'Consolas', monospace; font-size: 12px; padding: 2px 0; white-space: nowrap;">[${formatTimestamp(log.timestamp)}] <span style="color: ${levelColor}; font-weight: bold;">${log.level.padEnd(7)}</span>: ${escapeHtml(log.message)} <span style="color: #666;">(${log.module}:${log.line})</span></div>`;
    });

    container.innerHTML = html;
    container.scrollTop = 0;
}

async function clearLogs() {
    const buttons = `
        <button class="button button-secondary" onclick="closeNotification()">Cancel</button>
        <button class="button" style="background: #f44336;" onclick="closeNotification(); confirmClearLogs()">Clear</button>
    `;
    showNotification('Confirm Clear', 'Are you sure you want to clear all logs?', 'warning', buttons);
}

async function confirmClearLogs() {
    try {
        const response = await fetch('/api/logs/clear', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Success', 'Logs cleared successfully', 'success');
            refreshLogs();
        } else {
            showNotification('Error', 'Error clearing logs: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error', 'Error clearing logs: ' + error.message, 'error');
    }
}

