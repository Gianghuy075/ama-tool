// ==========================================================================
// GDP RegisterBot - Frontend Application Script
// ==========================================================================

// Application State
let currentTab = 'dashboard';
let botStatus = 'IDLE';
let logIndex = 0;
let isPolling = false;
let accountsList = [];
let originalAccountsJson = '';
let statusInterval = null;
let logsInterval = null;
let currentRunResults = [];
let selectedGroupFilter = '';

// DOM Elements
const sidebarStatusText = document.getElementById('sidebar-status-text');
const sidebarStatusDot = document.querySelector('.sidebar-status-card .card-status-dot');
const headerStatusBadge = document.getElementById('header-status-badge');
const headerStatusText = document.getElementById('header-status-text');
const pageTitle = document.getElementById('page-title');
const pageSubtitle = document.getElementById('page-subtitle');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    setupTabNavigation();
    setupDashboardControls();
    setupAccountsGrid();
    setupRegisteredAccounts();
    setupSaveResultsModal();
    setupConfigForm();
    setupLogsActions();
    
    // Initial fetch
    fetchStatus();
    fetchLogs();
    fetchAccounts();
    fetchConfig();
    
    // Setup product URL validation
    setupProductUrlValidation();
    
    // Setup XiaoWei phone mode controls
    setupXiaoWeiControls();
    
    // Start continuous polling (1s interval for status and logs)
    startPolling();
});

// ==========================================================================
// PRODUCT URL VALIDATION
// ==========================================================================
function setupProductUrlValidation() {
    const input = document.getElementById('input-product-url');
    const icon = document.getElementById('url-validation-icon');
    if (!input || !icon) return;
    
    input.addEventListener('input', () => {
        const val = input.value.trim();
        if (!val) {
            icon.className = 'url-validation-icon';
            icon.innerHTML = '';
            input.classList.remove('valid', 'invalid');
            return;
        }
        
        if (val.includes('amazon.co.jp')) {
            icon.className = 'url-validation-icon valid';
            icon.innerHTML = '<i class="bx bx-check-circle"></i>';
            input.classList.add('valid');
            input.classList.remove('invalid');
        } else {
            icon.className = 'url-validation-icon invalid';
            icon.innerHTML = '<i class="bx bx-x-circle"></i>';
            input.classList.add('invalid');
            input.classList.remove('valid');
        }
    });
}

// ==========================================================================
// TOAST NOTIFICATIONS
// ==========================================================================
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');
    const toastIcon = document.getElementById('toast-icon');
    
    toastMsg.textContent = message;
    
    // Reset classes
    toast.className = 'toast';
    toastIcon.className = 'bx toast-icon';
    
    if (type === 'success') {
        toast.classList.add('success');
        toastIcon.classList.add('bx-check-circle');
    } else if (type === 'error') {
        toast.classList.add('error');
        toastIcon.classList.add('bx-error-circle');
    }
    
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3500);
}

// ==========================================================================
// TAB NAVIGATION
// ==========================================================================
const tabSubtitles = {
    'dashboard': 'Giám sát và kiểm soát quá trình đăng ký tài khoản tự động',
    'accounts': 'Quản lý, thêm, sửa, xoá danh sách tài khoản cần đăng ký',
    'registered': 'Xem, lọc và tải về cơ sở dữ liệu tài khoản đã đăng ký thành công',
    'config': 'Chỉnh sửa cài đặt phần mềm, Gmail, Proxy và selectors',
    'logs': 'Xem nhật ký chi tiết các trình duyệt đang thực thi dưới dạng console'
};

const tabTitles = {
    'dashboard': 'Bảng Điều Khiển',
    'accounts': 'Quản Lý Tài Khoản',
    'registered': 'Quản Trị Tài Khoản',
    'config': 'Cấu Hình Hệ Thống',
    'logs': 'Nhật Ký Hệ Thống'
};

function setupTabNavigation() {
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.getAttribute('data-tab');
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    if (tabId === currentTab) return;
    
    // Update active tab menu link
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.getAttribute('data-tab') === tabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // Update active tab content panel
    document.querySelectorAll('.tab-content').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`tab-${tabId}`).classList.add('active');
    
    // Update page title
    pageTitle.textContent = tabTitles[tabId];
    pageSubtitle.textContent = tabSubtitles[tabId];
    
    currentTab = tabId;
    
    // Perform fresh fetch on switch to sync states
    if (tabId === 'accounts') {
        fetchAccounts();
    } else if (tabId === 'registered') {
        fetchRegisteredAccounts();
    } else if (tabId === 'config') {
        fetchConfig();
    }
}

// ==========================================================================
// DYNAMIC CONFIG FORMS
// ==========================================================================
function setupConfigForm() {
    const form = document.getElementById('config-form');
    const proxyToggle = document.getElementById('cfg-proxy_enable');
    const proxyFields = document.getElementById('proxy-fields');
    
    // Show/hide proxy details on toggle
    proxyToggle.addEventListener('change', () => {
        if (proxyToggle.checked) {
            proxyFields.classList.add('active');
        } else {
            proxyFields.classList.remove('active');
        }
    });
    
    // Headless browser switch label
    const headlessCheckbox = document.getElementById('cfg-headless');
    const headlessLabel = document.getElementById('headless-label');
    headlessCheckbox.addEventListener('change', () => {
        headlessLabel.textContent = headlessCheckbox.checked ? 'Ẩn trình duyệt' : 'Hiện trình duyệt';
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        saveConfig();
    });
}

async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        // Fill form fields
        document.getElementById('cfg-base_url').value = data.base_url || 'http://localhost:8000';
        document.getElementById('cfg-max_concurrent_tasks').value = data.max_concurrent_tasks || 3;
        
        // Product URL
        const productUrl = data.product_url || '';
        const cfgProductUrl = document.getElementById('cfg-product_url');
        if (cfgProductUrl) cfgProductUrl.value = productUrl;
        // Also pre-fill Dashboard product URL input
        const dashProductUrl = document.getElementById('input-product-url');
        if (dashProductUrl && !dashProductUrl.value) dashProductUrl.value = productUrl;
        
        const headlessCb = document.getElementById('cfg-headless');
        headlessCb.checked = !!data.headless;
        document.getElementById('headless-label').textContent = data.headless ? 'Ẩn trình duyệt' : 'Hiện trình duyệt';
        
        document.getElementById('cfg-gmail_address').value = data.gmail_address || '';
        document.getElementById('cfg-gmail_app_password').value = data.gmail_app_password || '';
        document.getElementById('cfg-imap_server').value = data.imap_server || 'imap.gmail.com';
        document.getElementById('cfg-otp_wait_seconds').value = data.otp_wait_seconds || 90;
        document.getElementById('cfg-delay_between_accounts').value = data.delay_between_accounts || 3;
        
        // Proxy settings
        const proxyEnable = !!(data.proxy && data.proxy.enable);
        const proxyToggle = document.getElementById('cfg-proxy_enable');
        proxyToggle.checked = proxyEnable;
        
        const proxyFields = document.getElementById('proxy-fields');
        if (proxyEnable) {
            proxyFields.classList.add('active');
        } else {
            proxyFields.classList.remove('active');
        }
        
        if (data.proxy) {
            document.getElementById('cfg-proxy_server').value = data.proxy.server || '';
            document.getElementById('cfg-proxy_change_ip_url').value = data.proxy.change_ip_url || '';
            document.getElementById('cfg-proxy_change_ip_delay').value = data.proxy.change_ip_delay || 15;
            document.getElementById('cfg-proxy_verify_ip').checked = !!data.proxy.verify_ip;
        }
        
        // Selectors
        if (data.selectors) {
            document.getElementById('cfg-sel-name').value = data.selectors.name || '';
            document.getElementById('cfg-sel-email').value = data.selectors.email || '';
            document.getElementById('cfg-sel-password').value = data.selectors.password || '';
            document.getElementById('cfg-sel-submit').value = data.selectors.submit || '';
            document.getElementById('cfg-sel-otp').value = data.selectors.otp || '';
            document.getElementById('cfg-sel-otp_submit').value = data.selectors.otp_submit || '';
        }
        
        // XiaoWei settings
        if (data.xiaowei) {
            const xwEnable = document.getElementById('cfg-xiaowei_enable');
            const xwFields = document.getElementById('xiaowei-fields');
            xwEnable.checked = !!data.xiaowei.enable;
            if (data.xiaowei.enable) {
                xwFields.classList.add('active');
            } else {
                xwFields.classList.remove('active');
            }
            document.getElementById('cfg-xiaowei_api_url').value = data.xiaowei.api_url || 'http://localhost:22222';
            document.getElementById('cfg-xiaowei_devices').value = data.xiaowei.devices || 'all';
            const typeSelect = document.getElementById('cfg-xiaowei_api_type');
            if (typeSelect) typeSelect.value = data.xiaowei.api_type || 'xiaowei';
            const otpSelect = document.getElementById('cfg-xiaowei_otp_source');
            if (otpSelect) otpSelect.value = data.xiaowei.otp_source || 'sms';
        }
    } catch (error) {
        console.error('Error fetching config:', error);
        showToast('Không tải được cấu hình hệ thống!', 'error');
    }
}

async function saveConfig() {
    const payload = {
        base_url: document.getElementById('cfg-base_url').value,
        product_url: document.getElementById('cfg-product_url').value || '',
        max_concurrent_tasks: parseInt(document.getElementById('cfg-max_concurrent_tasks').value),
        headless: document.getElementById('cfg-headless').checked,
        gmail_address: document.getElementById('cfg-gmail_address').value,
        gmail_app_password: document.getElementById('cfg-gmail_app_password').value,
        imap_server: document.getElementById('cfg-imap_server').value,
        otp_wait_seconds: parseInt(document.getElementById('cfg-otp_wait_seconds').value),
        delay_between_accounts: parseInt(document.getElementById('cfg-delay_between_accounts').value),
        proxy: {
            enable: document.getElementById('cfg-proxy_enable').checked,
            server: document.getElementById('cfg-proxy_server').value,
            change_ip_url: document.getElementById('cfg-proxy_change_ip_url').value,
            change_ip_delay: parseInt(document.getElementById('cfg-proxy_change_ip_delay').value) || 15,
            verify_ip: document.getElementById('cfg-proxy_verify_ip').checked
        },
        selectors: {
            name: document.getElementById('cfg-sel-name').value,
            email: document.getElementById('cfg-sel-email').value,
            password: document.getElementById('cfg-sel-password').value,
            submit: document.getElementById('cfg-sel-submit').value,
            otp: document.getElementById('cfg-sel-otp').value,
            otp_submit: document.getElementById('cfg-sel-otp_submit').value
        },
        xiaowei: {
            enable: document.getElementById('cfg-xiaowei_enable').checked,
            api_type: document.getElementById('cfg-xiaowei_api_type').value || 'xiaowei',
            api_url: document.getElementById('cfg-xiaowei_api_url').value || 'http://localhost:22222',
            devices: document.getElementById('cfg-xiaowei_devices').value || 'all',
            otp_source: document.getElementById('cfg-xiaowei_otp_source').value || 'sms',
            screenshot_dir: 'data/screenshots',
            tap_delay: [0.5, 1.5]
        }
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        
        if (result.success) {
            showToast('Lưu cấu hình hệ thống thành công!', 'success');
        } else {
            showToast('Lưu cấu hình thất bại: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showToast('Lỗi kết nối khi lưu cấu hình!', 'error');
    }
}

// ==========================================================================
// ACCOUNTS DATA GRID
// ==========================================================================
const btnSaveAccounts = document.getElementById('btn-save-accounts');
const btnAddAccount = document.getElementById('btn-add-account');

function setupAccountsGrid() {
    // Save accounts action
    btnSaveAccounts.addEventListener('click', saveAccountsData);
    
    // Add row action
    btnAddAccount.addEventListener('click', () => {
        addGridRow({ name: '', email: '', password: '', proxy: '' });
        checkGridDirty();
    });

    // Clear all action
    const btnClearAccountsGrid = document.getElementById('btn-clear-accounts-grid');
    if (btnClearAccountsGrid) {
        btnClearAccountsGrid.addEventListener('click', () => {
            showConfirmModal(
                'Xóa tất cả tài khoản',
                'Bạn có chắc chắn muốn xóa tất cả các dòng hiện tại khỏi danh sách tạm? (Bạn cần nhấn "Lưu Thay Đổi" để áp dụng vào file Excel)',
                () => {
                    accountsList = [];
                    renderAccountsGrid();
                    checkGridDirty();
                }
            );
        });
    }
    
    // File Upload Setup
    const dropzone = document.getElementById('excel-dropzone');
    const fileInput = document.getElementById('excel-file-input');
    
    dropzone.addEventListener('click', () => fileInput.click());
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
    
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFileUpload(fileInput.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/accounts/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'Tải danh sách Excel thành công!', 'success');
            if (data.accounts) {
                accountsList = data.accounts;
                renderAccountsGrid();
                checkGridDirty();
            }
        } else {
            showToast('Tải file Excel thất bại: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        showToast('Lỗi kết nối khi tải file Excel!', 'error');
    }
}


function normalizeAccountObject(acc) {
    return {
        name: (acc.name || '').trim(),
        email: (acc.email || '').trim(),
        password: (acc.password || '').trim(),
        proxy: (acc.proxy || '').trim()
    };
}

async function fetchAccounts() {
    try {
        const response = await fetch('/api/accounts');
        const data = await response.json();
        
        if (data.success) {
            accountsList = data.accounts;
            originalAccountsJson = JSON.stringify(data.accounts.map(normalizeAccountObject));
            renderAccountsGrid();
        } else {
            showToast('Không tải được danh sách tài khoản!', 'error');
        }
    } catch (error) {
        console.error('Error fetching accounts:', error);
    }
}

function renderAccountsGrid() {
    const tbody = document.getElementById('accounts-grid-body');
    tbody.innerHTML = '';
    
    if (accountsList.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row-accounts">
                <td colspan="6" class="text-center text-secondary">
                    Danh sách trống. Vui lòng bấm "Thêm Dòng" hoặc tải lên file accounts.xlsx
                </td>
            </tr>
        `;
        return;
    }
    
    accountsList.forEach((acc, index) => {
        addGridRow(acc, index + 1);
    });
    
    checkGridDirty();
}

function addGridRow(acc, rowNum = null) {
    const tbody = document.getElementById('accounts-grid-body');
    
    // Clear empty message row if exists
    const emptyRow = tbody.querySelector('.empty-row-accounts');
    if (emptyRow) {
        tbody.innerHTML = '';
    }
    
    if (rowNum === null) {
        rowNum = tbody.querySelectorAll('tr').length + 1;
    }
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="row-num-cell">${rowNum}</td>
        <td><input type="text" class="input-grid-name" value="${acc.name || ''}" placeholder="Nguyễn Văn A"></td>
        <td><input type="email" class="input-grid-email" value="${acc.email || ''}" placeholder="example@gmail.com"></td>
        <td><input type="text" class="input-grid-password" value="${acc.password || ''}" placeholder="Mật khẩu"></td>
        <td><input type="text" class="input-grid-proxy" value="${acc.proxy || ''}" placeholder="http://ip:port"></td>
        <td class="text-center">
            <button class="btn-delete-row" title="Xoá dòng"><i class="bx bx-trash"></i></button>
        </td>
    `;
    
    // Setup listeners inside cells to track changes and mark dirty
    const inputs = tr.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            checkGridDirty();
        });
    });
    
    // Delete action
    tr.querySelector('.btn-delete-row').addEventListener('click', () => {
        tr.remove();
        renumberGridRows();
        checkGridDirty();
    });
    
    tbody.appendChild(tr);
}

function renumberGridRows() {
    const tbody = document.getElementById('accounts-grid-body');
    const rows = tbody.querySelectorAll('tr');
    
    if (rows.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row-accounts">
                <td colspan="6" class="text-center text-secondary">
                    Danh sách trống. Vui lòng bấm "Thêm Dòng" hoặc tải lên file accounts.xlsx
                </td>
            </tr>
        `;
        return;
    }
    
    rows.forEach((row, i) => {
        row.querySelector('.row-num-cell').textContent = i + 1;
    });
}

function getGridData() {
    const tbody = document.getElementById('accounts-grid-body');
    if (!tbody) return [];
    
    const rows = tbody.querySelectorAll('tr');
    const data = [];
    
    if (tbody.querySelector('.empty-row-accounts')) {
        return [];
    }
    
    rows.forEach(row => {
        const nameEl = row.querySelector('.input-grid-name');
        const emailEl = row.querySelector('.input-grid-email');
        const passwordEl = row.querySelector('.input-grid-password');
        const proxyEl = row.querySelector('.input-grid-proxy');
        
        if (!emailEl) return; // Skip placeholder or invalid rows
        
        const name = nameEl ? nameEl.value : '';
        const email = emailEl.value;
        const password = passwordEl ? passwordEl.value : '';
        const proxy = proxyEl ? proxyEl.value : '';
        
        // Only require email to be filled, others can be optional but email is essential
        if (email.trim()) {
            data.push({ name, email, password, proxy });
        }
    });
    
    return data;
}

function checkGridDirty() {
    const currentData = getGridData().map(normalizeAccountObject);
    const currentJson = JSON.stringify(currentData);
    
    if (currentJson !== originalAccountsJson) {
        btnSaveAccounts.disabled = false;
        btnSaveAccounts.classList.remove('btn-secondary', 'btn-primary');
        btnSaveAccounts.classList.add('btn-success');
    } else {
        btnSaveAccounts.disabled = true;
        btnSaveAccounts.classList.remove('btn-success', 'btn-primary');
        btnSaveAccounts.classList.add('btn-secondary');
    }
}

async function saveAccountsData() {
    try {
        const gridData = getGridData();
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(gridData)
        });
        const result = await response.json();
        
        if (result.success) {
            showToast('Lưu thay đổi danh sách tài khoản thành công!', 'success');
            accountsList = gridData;
            originalAccountsJson = JSON.stringify(gridData.map(normalizeAccountObject));
            checkGridDirty();
        } else {
            showToast('Lưu danh sách thất bại: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('Error saving accounts:', error);
        showToast('Lỗi kết nối khi lưu danh sách tài khoản!', 'error');
    }
}

// ==========================================================================
// CONTROL & MONITORING (POLLING & BUTTON ACTIONS)
// ==========================================================================
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const progressPercent = document.getElementById('progress-percent');
const btnDownloadResults = document.getElementById('btn-download-results');

function setupDashboardControls() {
    btnStart.addEventListener('click', startBotExecution);
    btnStop.addEventListener('click', stopBotExecution);
}

async function startBotExecution() {
    // Check if there are unsaved grid edits and prompt
    const tbody = document.getElementById('accounts-grid-body');
    if (tbody && !btnSaveAccounts.disabled) {
        showConfirmModal(
            'Chưa lưu thay đổi',
            'Bạn có các thay đổi chưa lưu trong danh sách tài khoản. Những thay đổi này sẽ không được áp dụng khi chạy. Bạn có muốn tiếp tục chạy không?',
            () => {
                proceedWithStartBot();
            }
        );
    } else {
        proceedWithStartBot();
    }
}

async function proceedWithStartBot() {
    // Validate product URL
    const productUrlInput = document.getElementById('input-product-url');
    const productUrl = productUrlInput ? productUrlInput.value.trim() : '';
    
    if (!productUrl) {
        showToast('Vui lòng nhập link sản phẩm Amazon trước khi chạy!', 'error');
        if (productUrlInput) productUrlInput.focus();
        return;
    }
    
    if (!productUrl.includes('amazon.co.jp')) {
        showToast('Link sản phẩm phải là URL từ amazon.co.jp!', 'error');
        if (productUrlInput) productUrlInput.focus();
        return;
    }

    // Reset current run results on start
    currentRunResults = [];
    document.getElementById('btn-save-run-results').disabled = true;

    try {
        btnStart.disabled = true;
        const response = await fetch('/api/bot/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_name: '', product_url: productUrl })
        });
        const result = await response.json();
        
        if (result.success) {
            showToast('Bắt đầu quá trình đăng ký thành công!', 'success');
            fetchStatus(); // immediate check
        } else {
            showToast(result.message, 'error');
            btnStart.disabled = false;
        }
    } catch (error) {
        console.error('Error starting bot:', error);
        showToast('Không kết nối được với server điều khiển!', 'error');
        btnStart.disabled = false;
    }
}

async function stopBotExecution() {
    try {
        btnStop.disabled = true;
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showToast('Đang dừng các tác vụ...', 'success');
            fetchStatus(); // immediate check
        } else {
            showToast(result.message, 'error');
            btnStop.disabled = false;
        }
    } catch (error) {
        console.error('Error stopping bot:', error);
        showToast('Không kết nối được với server điều khiển!', 'error');
        btnStop.disabled = false;
    }
}

function startPolling() {
    isPolling = true;
    
    // Status polling every 1.5 seconds
    statusInterval = setInterval(fetchStatus, 1500);
    
    // Logs polling every 1 second
    logsInterval = setInterval(fetchLogs, 1000);
}

function stopPolling() {
    isPolling = false;
    if (statusInterval) clearInterval(statusInterval);
    if (logsInterval) clearInterval(logsInterval);
}

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update states
        if (data.results && data.results.length > 0) {
            currentRunResults = data.results;
        }
        
        updateUIState(data.status);
        updateUIStats(data.total, data.success, data.failed);
        updateUIProgress(data.total, data.success, data.failed, data.status);
        updateUILiveResults(data.results);
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateUIState(status) {
    botStatus = status;
    
    // Header Status Badge styling
    headerStatusBadge.className = 'status-badge';
    headerStatusBadge.classList.add(status.toLowerCase());
    headerStatusText.textContent = status;
    
    // Sidebar status indicator
    sidebarStatusDot.className = 'card-status-dot';
    sidebarStatusDot.classList.add(status.toLowerCase());
    
    const productUrlInput = document.getElementById('input-product-url');

    if (status === 'RUNNING') {
        sidebarStatusText.textContent = 'Đang Chạy...';
        btnStart.disabled = true;
        btnStop.disabled = false;
        if (productUrlInput) productUrlInput.disabled = true;
        btnDownloadResults.classList.add('disabled');
        btnDownloadResults.style.pointerEvents = 'none';
        btnDownloadResults.style.opacity = '0.5';
        document.getElementById('btn-save-run-results').disabled = true;
    } else if (status === 'STOPPING') {
        sidebarStatusText.textContent = 'Đang Dừng...';
        btnStart.disabled = true;
        btnStop.disabled = true;
        if (productUrlInput) productUrlInput.disabled = true;
        btnDownloadResults.classList.add('disabled');
        btnDownloadResults.style.pointerEvents = 'none';
        btnDownloadResults.style.opacity = '0.5';
        document.getElementById('btn-save-run-results').disabled = true;
    } else {
        sidebarStatusText.textContent = 'Đang Dừng';
        btnStart.disabled = false;
        btnStop.disabled = true;
        if (productUrlInput) productUrlInput.disabled = false;
        btnDownloadResults.classList.remove('disabled');
        btnDownloadResults.style.pointerEvents = 'auto';
        btnDownloadResults.style.opacity = '1';
        
        const hasResults = currentRunResults && currentRunResults.length > 0;
        document.getElementById('btn-save-run-results').disabled = !hasResults;
    }
}

function updateUIStats(total, success, failed) {
    document.getElementById('stats-total').textContent = total;
    document.getElementById('stats-success').textContent = success;
    document.getElementById('stats-failed').textContent = failed;
    
    // Calculate rate
    const processed = success + failed;
    let rate = 0;
    if (processed > 0) {
        rate = Math.round((success / processed) * 100);
    }
    document.getElementById('stats-rate').textContent = `${rate}%`;
}

function updateUIProgress(total, success, failed, status) {
    const processed = success + failed;
    
    if (status === 'IDLE' && processed === 0) {
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        progressText.textContent = 'Chưa chạy';
        return;
    }
    
    let percent = 0;
    if (total > 0) {
        percent = Math.round((processed / total) * 100);
    }
    
    progressBar.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
    
    if (status === 'RUNNING') {
        progressText.textContent = `Đang xử lý: ${processed}/${total} tài khoản`;
    } else if (status === 'STOPPING') {
        progressText.textContent = `Đang huỷ tiến trình... (${processed}/${total})`;
    } else {
        progressText.textContent = `Đã hoàn tất: ${processed}/${total} tài khoản`;
    }
}

function updateUILiveResults(results) {
    const tbody = document.querySelector('#live-results-table tbody');
    if (!tbody) return;
    
    if (results.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="5" class="text-center text-secondary">Chưa chạy hoặc chưa có tài khoản nào được đăng ký</td>
            </tr>
        `;
        return;
    }
    
    // Sort results by timestamp descending to show latest at top
    const sorted = [...results].sort((a, b) => {
        return new Date(b.timestamp) - new Date(a.timestamp);
    });
    
    tbody.innerHTML = '';
    sorted.forEach(r => {
        const tr = document.createElement('tr');
        const isSuccess = r.status === 'SUCCESS';
        
        tr.innerHTML = `
            <td><strong>${escapeHtml(r.name)}</strong></td>
            <td>${escapeHtml(r.email)}</td>
            <td>
                <span class="status-badge ${isSuccess ? 'running' : 'stopping'}" style="padding: 2px 8px; font-size: 11px;">
                    ${r.status}
                </span>
            </td>
            <td class="${isSuccess ? 'text-green' : 'text-red'}" style="font-size: 13px;">${escapeHtml(r.note || '')}</td>
            <td style="font-size: 12px;" class="text-muted">${escapeHtml(r.timestamp)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ==========================================================================
// REAL-TIME LOGGER
// ==========================================================================
const miniConsole = document.getElementById('mini-console');
const logsConsole = document.getElementById('logs-console');
const logsFilterInput = document.getElementById('logs-filter-input');
const btnClearLogs = document.getElementById('btn-clear-logs');
const btnAutoscroll = document.getElementById('btn-autoscroll-logs');

let filterKeyword = '';

function setupLogsActions() {
    btnClearLogs.addEventListener('click', () => {
        miniConsole.innerHTML = '';
        logsConsole.innerHTML = '<div class="terminal-line system-line">[Hệ thống] Logs đã được xoá.</div>';
        logIndex = 0;
    });
    
    logsFilterInput.addEventListener('input', () => {
        filterKeyword = logsFilterInput.value.toLowerCase();
        applyLogsFilter();
    });
}

async function fetchLogs() {
    try {
        const response = await fetch(`/api/logs?since=${logIndex}`);
        const data = await response.json();
        
        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(line => {
                appendLogLine(line);
            });
            logIndex = data.next_index;
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

function appendLogLine(line) {
    // Clean escape characters or add styling if necessary
    const isSuccess = line.includes('SUCCESS') || line.includes('✅');
    const isError = line.includes('Error') || line.includes('[ERROR]') || line.includes('❌') || line.includes('Lỗi');
    const isWarning = line.includes('Timeout') || line.includes('[WARNING]') || line.includes('⚠️') || line.includes('Cảnh báo');
    
    let lineClass = '';
    if (isSuccess) lineClass = 'success-line';
    else if (isError) lineClass = 'error-line';
    else if (isWarning) lineClass = 'warning-line';
    
    const escaped = escapeHtml(line);
    const lineHtml = `<div class="terminal-line ${lineClass}">${escaped}</div>`;
    
    // Append to mini console (always show latest and limit length)
    miniConsole.insertAdjacentHTML('beforeend', lineHtml);
    if (miniConsole.children.length > 50) {
        miniConsole.removeChild(miniConsole.firstChild);
    }
    miniConsole.scrollTop = miniConsole.scrollHeight;
    
    // Append to full console
    logsConsole.insertAdjacentHTML('beforeend', lineHtml);
    
    // Apply filter dynamically if active
    if (filterKeyword) {
        const lastChild = logsConsole.lastElementChild;
        const text = lastChild.textContent.toLowerCase();
        if (!text.includes(filterKeyword)) {
            lastChild.style.display = 'none';
        }
    }
    
    // Scroll full console if autoscroll is enabled
    if (btnAutoscroll.checked) {
        logsConsole.scrollTop = logsConsole.scrollHeight;
    }
}

function applyLogsFilter() {
    const lines = logsConsole.querySelectorAll('.terminal-line');
    lines.forEach(line => {
        const text = line.textContent.toLowerCase();
        if (text.includes(filterKeyword) || line.classList.contains('system-line')) {
            line.style.display = 'block';
        } else {
            line.style.display = 'none';
        }
    });
}

// ==========================================================================
// CUSTOM DIALOG / MODAL HELPERS
// ==========================================================================
function showConfirmModal(title, message, onConfirm) {
    const modal = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-message');
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    const okBtn = document.getElementById('confirm-modal-ok');
    
    titleEl.innerHTML = `<i class="bx bx-help-circle text-primary" style="margin-right: 8px; font-size: 20px; vertical-align: middle;"></i>` + title;
    msgEl.textContent = message;
    
    const closeModal = () => {
        modal.classList.remove('active');
        // Clean listeners by replacing elements with clones
        okBtn.replaceWith(okBtn.cloneNode(true));
        cancelBtn.replaceWith(cancelBtn.cloneNode(true));
    };
    
    // Select the new clone elements to bind event listeners
    const newOkBtn = document.getElementById('confirm-modal-ok');
    const newCancelBtn = document.getElementById('confirm-modal-cancel');
    
    newOkBtn.addEventListener('click', () => {
        onConfirm();
        closeModal();
    });
    
    newCancelBtn.addEventListener('click', closeModal);
    modal.classList.add('active');
}

function setupSaveResultsModal() {
    const btnSaveRunResults = document.getElementById('btn-save-run-results');
    const modal = document.getElementById('save-results-modal');
    const cancelBtn = document.getElementById('save-results-cancel');
    const confirmBtn = document.getElementById('save-results-confirm');
    const existingGroupSelect = document.getElementById('save-existing-group');
    const newGroupNameInput = document.getElementById('save-new-group-name');
    
    if (btnSaveRunResults) {
        btnSaveRunResults.addEventListener('click', async () => {
            // Fetch existing groups to populate select
            try {
                const response = await fetch('/api/registered/groups');
                const data = await response.json();
                if (data.success) {
                    existingGroupSelect.innerHTML = '<option value="">-- Tạo nhóm mới --</option>';
                    data.groups.forEach(g => {
                        const opt = document.createElement('option');
                        opt.value = g;
                        opt.textContent = g;
                        existingGroupSelect.appendChild(opt);
                    });
                }
            } catch (error) {
                console.error('Error fetching groups:', error);
            }
            
            newGroupNameInput.value = '';
            modal.classList.add('active');
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            const selectedExisting = existingGroupSelect.value;
            const inputNew = newGroupNameInput.value.trim();
            
            let groupName = '';
            if (selectedExisting) {
                groupName = selectedExisting;
            } else if (inputNew) {
                groupName = inputNew;
            } else {
                alert('Vui lòng chọn một nhóm hoặc nhập tên nhóm mới!');
                return;
            }
            
            confirmBtn.disabled = true;
            
            try {
                const response = await fetch('/api/registered/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        group_name: groupName,
                        results: currentRunResults
                    })
                });
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                    modal.classList.remove('active');
                    btnSaveRunResults.disabled = true; // prevent saving again
                    currentRunResults = []; // clear in-memory results
                    if (currentTab === 'registered') {
                        fetchRegisteredAccounts();
                    }
                } else {
                    showToast('Lưu kết quả thất bại: ' + result.message, 'error');
                }
            } catch (error) {
                console.error('Error saving results:', error);
                showToast('Lỗi kết nối khi lưu kết quả!', 'error');
            } finally {
                confirmBtn.disabled = false;
            }
        });
    }
}

// ==========================================================================
// REGISTERED ACCOUNTS MANAGEMENT
// ==========================================================================
let registeredAccountsList = [];
let registeredFilterKeyword = '';

function setupRegisteredAccounts() {
    const filterInput = document.getElementById('registered-filter-input');
    const groupFilter = document.getElementById('registered-group-filter');
    const btnClearRegistered = document.getElementById('btn-clear-registered');
    
    if (filterInput) {
        filterInput.addEventListener('input', () => {
            registeredFilterKeyword = filterInput.value.toLowerCase();
            renderRegisteredGrid();
        });
    }

    if (groupFilter) {
        groupFilter.addEventListener('change', () => {
            selectedGroupFilter = groupFilter.value;
            renderRegisteredGrid();
        });
    }
    
    if (btnClearRegistered) {
        btnClearRegistered.addEventListener('click', () => {
            showConfirmModal(
                'Xóa cơ sở dữ liệu',
                'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản đã đăng ký trong cơ sở dữ liệu? Hành động này không thể hoàn tác!',
                () => {
                    clearRegisteredAccounts();
                }
            );
        });
    }
}

async function fetchRegisteredAccounts() {
    try {
        const response = await fetch('/api/registered');
        const data = await response.json();
        if (data.success) {
            registeredAccountsList = data.accounts || [];
            
            // Populate group filter dropdown with unique groups from list
            const groupFilter = document.getElementById('registered-group-filter');
            if (groupFilter) {
                const uniqueGroups = [...new Set(registeredAccountsList.map(acc => acc.group).filter(Boolean))];
                const currentSelected = groupFilter.value;
                groupFilter.innerHTML = '<option value="">Tất cả</option>';
                uniqueGroups.forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = g;
                    opt.textContent = g;
                    if (g === currentSelected) {
                        opt.selected = true;
                    }
                    groupFilter.appendChild(opt);
                });
                selectedGroupFilter = groupFilter.value;
            }
            
            renderRegisteredGrid();
        } else {
            showToast('Không tải được danh sách tài khoản đã đăng ký!', 'error');
        }
    } catch (error) {
        console.error('Error fetching registered accounts:', error);
        showToast('Lỗi kết nối khi tải danh sách tài khoản đã đăng ký!', 'error');
    }
}

function renderRegisteredGrid() {
    const tbody = document.getElementById('registered-grid-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    // Filter list by selected group and search query
    const filtered = registeredAccountsList.filter(acc => {
        // 1. Group filter condition
        if (selectedGroupFilter && acc.group !== selectedGroupFilter) return false;
        
        // 2. Search keyword condition
        if (!registeredFilterKeyword) return true;
        const group = (acc.group || '').toLowerCase();
        const name = (acc.name || '').toLowerCase();
        const email = (acc.email || '').toLowerCase();
        const password = (acc.password || '').toLowerCase();
        const proxy = (acc.proxy || '').toLowerCase();
        const status = (acc.status || '').toLowerCase();
        const note = (acc.note || '').toLowerCase();
        const timestamp = (acc.timestamp || '').toLowerCase();
        return group.includes(registeredFilterKeyword) ||
               name.includes(registeredFilterKeyword) || 
               email.includes(registeredFilterKeyword) || 
               password.includes(registeredFilterKeyword) || 
               proxy.includes(registeredFilterKeyword) || 
               status.includes(registeredFilterKeyword) || 
               note.includes(registeredFilterKeyword) || 
               timestamp.includes(registeredFilterKeyword);
    });
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="8" class="text-center text-secondary">
                    ${registeredFilterKeyword || selectedGroupFilter ? 'Không tìm thấy tài khoản phù hợp' : 'Chưa có tài khoản nào được đăng ký'}
                </td>
            </tr>
        `;
        return;
    }
    
    filtered.forEach((acc, index) => {
        const tr = document.createElement('tr');
        const isSuccess = acc.status === 'SUCCESS';
        
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${escapeHtml(acc.group || 'Mặc định')}</strong></td>
            <td><strong>${escapeHtml(acc.name)}</strong></td>
            <td>${escapeHtml(acc.email)}</td>
            <td>${escapeHtml(acc.password)}</td>
            <td>${escapeHtml(acc.proxy || '')}</td>
            <td>
                <span class="status-badge ${isSuccess ? 'running' : 'stopping'}" style="padding: 2px 8px; font-size: 11px;">
                    ${escapeHtml(acc.status)}
                </span>
            </td>
            <td><span class="text-muted" style="font-size: 12px;">${escapeHtml(acc.timestamp)}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

async function clearRegisteredAccounts() {
    try {
        const response = await fetch('/api/registered/clear', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast(data.message, 'success');
            registeredAccountsList = [];
            
            // Clear group filter select options
            const groupFilter = document.getElementById('registered-group-filter');
            if (groupFilter) {
                groupFilter.innerHTML = '<option value="">Tất cả</option>';
                selectedGroupFilter = '';
            }
            
            renderRegisteredGrid();
        } else {
            showToast('Xóa dữ liệu thất bại: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error clearing registered accounts:', error);
        showToast('Lỗi kết nối khi xóa dữ liệu!', 'error');
    }
}

// ==========================================================================
// XIAOWEI PHONE MODE CONTROLS
// ==========================================================================
function setupXiaoWeiControls() {
    const xwToggle = document.getElementById('cfg-xiaowei_enable');
    const xwFields = document.getElementById('xiaowei-fields');
    const btnTest = document.getElementById('btn-test-xiaowei');
    const btnDiagnose = document.getElementById('btn-diagnose-xiaowei');
    
    if (xwToggle && xwFields) {
        xwToggle.addEventListener('change', () => {
            if (xwToggle.checked) {
                xwFields.classList.add('active');
            } else {
                xwFields.classList.remove('active');
            }
        });
    }
    
    if (btnTest) {
        btnTest.addEventListener('click', testXiaoWeiConnection);
    }
    
    if (btnDiagnose) {
        btnDiagnose.addEventListener('click', runXiaoWeiDiagnostics);
    }
}

async function testXiaoWeiConnection() {
    const apiUrl = document.getElementById('cfg-xiaowei_api_url').value.trim();
    const apiType = document.getElementById('cfg-xiaowei_api_type').value || 'xiaowei';
    const btnTest = document.getElementById('btn-test-xiaowei');
    const devicesPanel = document.getElementById('xiaowei-devices-panel');
    const devicesList = document.getElementById('xiaowei-devices-list');
    
    if (!apiUrl) {
        showToast('Vui lòng nhập URL API XiaoWei/Phone Farm!', 'error');
        return;
    }
    
    btnTest.disabled = true;
    btnTest.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Đang kiểm tra...';
    
    try {
        const response = await fetch('/api/xiaowei/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_url: apiUrl, api_type: apiType })
        });
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
            devicesPanel.style.display = 'block';
            renderXiaoWeiDevices(result.devices || []);
        } else {
            showToast(result.message || 'Kết nối thất bại!', 'error');
            devicesPanel.style.display = 'block';
            devicesList.innerHTML = '<p class="text-red text-sm"><i class="bx bx-x-circle"></i> ' + escapeHtml(result.message) + '</p>';
        }
    } catch (error) {
        console.error('Error testing XiaoWei:', error);
        showToast('Không thể kết nối tới server!', 'error');
        devicesPanel.style.display = 'block';
        devicesList.innerHTML = '<p class="text-red text-sm"><i class="bx bx-x-circle"></i> Lỗi kết nối mạng</p>';
    } finally {
        btnTest.disabled = false;
        btnTest.innerHTML = '<i class="bx bx-plug"></i> Kiểm Tra';
    }
}

function renderXiaoWeiDevices(devices) {
    const container = document.getElementById('xiaowei-devices-list');
    if (!container) return;
    
    if (!devices || devices.length === 0) {
        container.innerHTML = '<p class="text-secondary text-sm">Không tìm thấy thiết bị nào đang kết nối.</p>';
        return;
    }
    
    let html = '';
    devices.forEach((d, i) => {
        const serial = d.serial || d.Serial || d.id || d.name || `Device ${i+1}`;
        const model = d.model || d.Model || d.deviceModel || '';
        const status = d.status || d.Status || 'online';
        const isOnline = status.toLowerCase().includes('online') || status === '' || status === 'connected';
        
        html += `
            <div class="xiaowei-device-card ${isOnline ? 'online' : 'offline'}">
                <div class="device-status-dot ${isOnline ? 'online' : 'offline'}"></div>
                <div class="device-info">
                    <span class="device-serial">${escapeHtml(String(serial))}</span>
                    <span class="device-model">${escapeHtml(String(model))}</span>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function runXiaoWeiDiagnostics() {
    const apiUrl = document.getElementById('cfg-xiaowei_api_url').value.trim();
    const apiType = document.getElementById('cfg-xiaowei_api_type').value || 'xiaowei';
    const device = document.getElementById('cfg-xiaowei_devices').value.trim() || 'all';
    const btnDiagnose = document.getElementById('btn-diagnose-xiaowei');
    const panel = document.getElementById('xiaowei-diagnostics-panel');
    const container = document.getElementById('xiaowei-diagnostics-results');

    if (!apiUrl) {
        showToast('Vui lòng nhập URL API XiaoWei trước khi chẩn đoán!', 'error');
        return;
    }

    btnDiagnose.disabled = true;
    btnDiagnose.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Đang chạy...';
    panel.style.display = 'block';
    container.innerHTML = '<p class="text-secondary text-sm">Đang chạy diagnostics XiaoWei...</p>';

    try {
        const response = await fetch('/api/xiaowei/diagnostics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_url: apiUrl, api_type: apiType, device })
        });
        const report = await response.json();
        renderXiaoWeiDiagnostics(report);
        if (report.overall_success) {
            showToast('Diagnostics XiaoWei đã pass smoke test!', 'success');
        } else {
            showToast('Diagnostics XiaoWei phát hiện một số bước chưa pass.', 'error');
        }
    } catch (error) {
        console.error('Error running XiaoWei diagnostics:', error);
        container.innerHTML = '<p class="text-red text-sm"><i class="bx bx-x-circle"></i> Không thể chạy diagnostics.</p>';
        showToast('Không thể chạy diagnostics XiaoWei!', 'error');
    } finally {
        btnDiagnose.disabled = false;
        btnDiagnose.innerHTML = '<i class="bx bx-stethoscope"></i> Chẩn Đoán';
    }
}

function renderXiaoWeiDiagnostics(report) {
    const container = document.getElementById('xiaowei-diagnostics-results');
    if (!container) return;

    const overallSuccess = !!report.overall_success;
    const backendLabel = report.backend_label || report.backend || 'unknown';
    const selectedDevice = report.selected_device || 'N/A';
    const reportPath = report.report_path || 'N/A';
    const steps = Array.isArray(report.steps) ? report.steps : [];

    let html = `
        <div class="xiaowei-diagnostics-summary ${overallSuccess ? 'success' : 'fail'}">
            <strong>${overallSuccess ? 'PASS' : 'CHECK REQUIRED'}</strong><br>
            Backend: ${escapeHtml(String(backendLabel))}<br>
            Device: ${escapeHtml(String(selectedDevice))}<br>
            Report: ${escapeHtml(String(reportPath))}
        </div>
    `;

    if (steps.length === 0) {
        html += '<p class="text-secondary text-sm">Không có bước diagnostics nào được trả về.</p>';
    } else {
        steps.forEach((step) => {
            html += `
                <div class="xiaowei-diagnostic-step ${step.success ? 'pass' : 'fail'}">
                    <div class="xiaowei-diagnostic-title">
                        <i class="bx ${step.success ? 'bx-check-circle text-green' : 'bx-x-circle text-red'}"></i>
                        <span>${escapeHtml(String(step.name || 'step'))}</span>
                    </div>
                    <div class="xiaowei-diagnostic-detail">${escapeHtml(String(step.detail || ''))}</div>
                </div>
            `;
        });
    }

    container.innerHTML = html;
}
