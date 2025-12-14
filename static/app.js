// Global variables
let variablesEditor, templateEditor;
let uploadedData = null;
let currentTemplateId = null;
let allTemplates = [];
let generatedConfigs = [];

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
            uploadedData = result.data;
            document.getElementById('generateBtn').disabled = false;
            document.getElementById('uploadArea').innerHTML = `
                <div class="upload-icon">✅</div>
                <div style="color: #4caf50; font-size: 1.1em; margin-bottom: 8px;">
                    File uploaded successfully: ${file.name}
                </div>
                <div style="color: #999; font-size: 0.9em;">
                    ${result.data.length} rows loaded
                </div>
            `;
        } else {
            alert('Error uploading file: ' + result.error);
        }
    } catch (error) {
        alert('Error uploading file: ' + error.message);
    }
}

async function generateConfigs() {
    if (!uploadedData) {
        alert('Please upload an Excel file first');
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
            displayConfigs(result.configs);
            document.getElementById('downloadAllBtn').disabled = false;
        } else {
            alert('Error generating configs: ' + result.error);
        }
    } catch (error) {
        alert('Error generating configs: ' + error.message);
    }
}

function displayConfigs(configs) {
    const resultsContainer = document.getElementById('configResults');

    if (configs.length === 0) {
        resultsContainer.innerHTML = '<div class="info-box">No configs generated</div>';
        return;
    }

    resultsContainer.innerHTML = configs.map((config, index) => {
        if (config.success) {
            return `
                <div class="config-item">
                    <div class="config-header">
                        <div class="config-title">
                            Config #${index + 1} - ${config.row.host_type}/${config.row.vendor}/${config.row.os}
                        </div>
                        <div>
                            <span class="success-badge">Success</span>
                            <button class="button button-secondary" style="margin-left: 10px;" onclick="copyConfig(${index})">Copy</button>
                        </div>
                    </div>
                    <div class="config-output">${escapeHtml(config.config)}</div>
                </div>
            `;
        } else {
            return `
                <div class="config-item">
                    <div class="config-header">
                        <div class="config-title">
                            Config #${index + 1} - ${config.row.host_type || 'N/A'}/${config.row.vendor || 'N/A'}/${config.row.os || 'N/A'}
                        </div>
                        <span class="error-badge">Error</span>
                    </div>
                    <div style="color: #f44336; padding: 10px;">${config.error}</div>
                </div>
            `;
        }
    }).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyConfig(index) {
    const config = generatedConfigs[index];
    if (config && config.success) {
        navigator.clipboard.writeText(config.config).then(() => {
            alert('Config copied to clipboard!');
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    }
}

function downloadAllConfigs() {
    const successConfigs = generatedConfigs.filter(c => c.success);

    if (successConfigs.length === 0) {
        alert('No successful configs to download');
        return;
    }

    const content = successConfigs.map((config, index) => {
        return `! ============================================\n` +
               `! Config #${index + 1} - ${config.row.host_type}/${config.row.vendor}/${config.row.os}\n` +
               `! Template: ${config.template_name}\n` +
               `! ============================================\n\n` +
               config.config + '\n\n';
    }).join('\n');

    const blob = new Blob([content], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'all_configs.txt';
    a.click();
    URL.revokeObjectURL(url);
}

function downloadTemplateExcel() {
    if (!currentTemplateId) {
        alert('Please select a template first');
        return;
    }

    const url = `/api/download-template-excel/${currentTemplateId}`;
    window.location.href = url;
}

// ========== Template Manager Tab ==========
async function initializeTemplateManager() {
    await loadMetadata();
    await loadTemplates();
}

async function loadMetadata() {
    try {
        const [hostTypes, vendors, osTypes] = await Promise.all([
            fetch('/api/host-types').then(r => r.json()),
            fetch('/api/vendors').then(r => r.json()),
            fetch('/api/os-types').then(r => r.json())
        ]);

        populateSelect('filterHostType', hostTypes);
        populateSelect('filterVendor', vendors);
    } catch (error) {
        console.error('Error loading metadata:', error);
    }
}

function populateSelect(selectId, options) {
    const select = document.getElementById(selectId);
    const currentValue = select.value;

    options.forEach(option => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        select.appendChild(opt);
    });

    if (currentValue) {
        select.value = currentValue;
    }
}

async function loadTemplates() {
    try {
        const response = await fetch('/api/templates');
        allTemplates = await response.json();
        filterTemplates();
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

function filterTemplates() {
    const hostType = document.getElementById('filterHostType').value;
    const vendor = document.getElementById('filterVendor').value;
    const os = document.getElementById('filterOS').value;

    const filtered = allTemplates.filter(t => {
        return (!hostType || t.host_type === hostType) &&
               (!vendor || t.vendor === vendor) &&
               (!os || t.os === os);
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
        <div class="template-item" onclick="selectTemplate(${t.id})">
            <div class="template-item-title">${t.name}</div>
            <div class="template-item-meta">
                ${t.host_type} | ${t.vendor} | ${t.os}
            </div>
        </div>
    `).join('');
}

async function selectTemplate(templateId) {
    try {
        const response = await fetch(`/api/templates/${templateId}`);
        const template = await response.json();

        currentTemplateId = templateId;

        document.querySelectorAll('.template-item').forEach(item => {
            item.classList.remove('selected');
        });
        event.target.closest('.template-item').classList.add('selected');

        showTemplateForm(template);
    } catch (error) {
        console.error('Error loading template:', error);
    }
}

async function showTemplateForm(template = null) {
    const formContainer = document.getElementById('templateForm');
    const actionsContainer = document.getElementById('formActions');

    const hostTypes = await fetch('/api/host-types').then(r => r.json());
    const vendors = await fetch('/api/vendors').then(r => r.json());

    formContainer.innerHTML = `
        <div class="form-group">
            <label class="form-label">Template Name *</label>
            <input type="text" class="form-input" id="templateName" value="${template ? template.name : ''}" required>
        </div>

        <div class="form-group">
            <label class="form-label">Host Type *</label>
            <select class="form-select" id="templateHostType" required>
                ${hostTypes.map(ht => `<option value="${ht}" ${template && template.host_type === ht ? 'selected' : ''}>${ht}</option>`).join('')}
            </select>
        </div>

        <div class="form-group">
            <label class="form-label">Vendor *</label>
            <select class="form-select" id="templateVendor" onchange="loadOSOptions()" required>
                ${vendors.map(v => `<option value="${v}" ${template && template.vendor === v ? 'selected' : ''}>${v}</option>`).join('')}
            </select>
        </div>

        <div class="form-group">
            <label class="form-label">OS *</label>
            <select class="form-select" id="templateOS" required>
                ${template ? `<option value="${template.os}" selected>${template.os}</option>` : ''}
            </select>
        </div>

        <div class="form-group">
            <label class="form-label">Description</label>
            <input type="text" class="form-input" id="templateDescription" value="${template ? template.description || '' : ''}">
        </div>

        <div class="form-group">
            <label class="form-label">Template Content (Jinja2) *</label>
            <textarea class="form-textarea" id="templateContent" rows="20" required>${template ? template.template_content : ''}</textarea>
        </div>
    `;

    actionsContainer.style.display = 'flex';

    if (template) {
        document.getElementById('deleteBtn').style.display = 'block';
        loadOSOptions();
    } else {
        document.getElementById('deleteBtn').style.display = 'none';
        loadOSOptions();
    }
}

async function loadOSOptions() {
    const vendor = document.getElementById('templateVendor').value;
    const osSelect = document.getElementById('templateOS');
    const currentOS = osSelect.value;

    const osTypes = await fetch(`/api/os-types?vendor=${vendor}`).then(r => r.json());

    osSelect.innerHTML = osTypes.map(os => `
        <option value="${os}" ${os === currentOS ? 'selected' : ''}>${os}</option>
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
    const vendor = document.getElementById('templateVendor').value;
    const os = document.getElementById('templateOS').value;
    const description = document.getElementById('templateDescription').value;
    const content = document.getElementById('templateContent').value;

    if (!name || !hostType || !vendor || !os || !content) {
        alert('Please fill in all required fields');
        return;
    }

    const data = {
        name,
        host_type: hostType,
        vendor,
        os,
        description,
        template_content: content
    };

    try {
        let response;
        if (currentTemplateId) {
            response = await fetch(`/api/templates/${currentTemplateId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
        } else {
            response = await fetch('/api/templates', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
        }

        const result = await response.json();

        if (result.success) {
            alert('Template saved successfully!');
            await loadTemplates();
            if (!currentTemplateId && result.template_id) {
                currentTemplateId = result.template_id;
            }
        } else {
            alert('Error saving template: ' + result.error);
        }
    } catch (error) {
        alert('Error saving template: ' + error.message);
    }
}

async function deleteTemplate() {
    if (!currentTemplateId) return;

    if (!confirm('Are you sure you want to delete this template?')) return;

    try {
        const response = await fetch(`/api/templates/${currentTemplateId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('Template deleted successfully!');
            currentTemplateId = null;
            await loadTemplates();
            cancelEdit();
        } else {
            alert('Error deleting template: ' + result.error);
        }
    } catch (error) {
        alert('Error deleting template: ' + error.message);
    }
}

function cancelEdit() {
    currentTemplateId = null;
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

// ========== Metadata Management ==========

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
        const response = await fetch('/api/vendors');
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
        const response = await fetch('/api/vendors', {
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
        const response = await fetch('/api/vendors/delete', {
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
    await loadOSVendorDropdown();
}

function closeOSManager() {
    document.getElementById('osModal').style.display = 'none';
}

async function loadOSList() {
    try {
        const response = await fetch('/api/os-types');
        const osTypes = await response.json();

        document.getElementById('osList').innerHTML = osTypes.map(os => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #2d2d30; border-radius: 4px; margin-bottom: 8px;">
                <span style="color: #ccc;">${os.vendor} - ${os.name}</span>
                <button onclick="deleteOS('${os.vendor.replace(/'/g, "\\'")}', '${os.name.replace(/'/g, "\\'")}')" style="background: #f44336; border: none; color: white; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
            </div>
        `).join('') || '<div style="color: #999; padding: 20px; text-align: center;">No OS types</div>';
    } catch (error) {
        console.error('Error loading OS types:', error);
        alert('Error loading OS types: ' + error.message);
    }
}

async function loadOSVendorDropdown() {
    try {
        const response = await fetch('/api/vendors');
        const vendors = await response.json();

        const select = document.getElementById('newOSVendor');
        select.innerHTML = '<option value="">Select vendor</option>' +
            vendors.map(v => `<option value="${v}">${v}</option>`).join('');
    } catch (error) {
        console.error('Error loading vendors:', error);
    }
}

async function addOS() {
    const vendorSelect = document.getElementById('newOSVendor');
    const input = document.getElementById('newOS');
    const vendor = vendorSelect.value;
    const name = input.value.trim();

    if (!vendor) {
        alert('Please select a vendor');
        return;
    }

    if (!name) {
        alert('Please enter an OS name');
        return;
    }

    try {
        const response = await fetch('/api/os-types', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({vendor, name})
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

async function deleteOS(vendor, name) {
    if (!confirm(`Delete "${vendor} - ${name}"? This may affect existing templates.`)) return;

    try {
        const response = await fetch('/api/os-types/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({vendor, name})
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
