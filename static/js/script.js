/**
 * Device Management Application
 * Frontend script for managing device discovery and interaction
 */

// Global configuration
const API_BASE_URL = 'http://localhost:5000/api';
const IS_MOBILE = window.innerWidth <= 768;

// DOM elements initialized on document load
let sidebar, mainContent, toggleButtonExternal, toggleButtonInside;
let addDeviceModal, passwordVerifyModal, editDeviceModal;
let deviceNameInput, deviceIdInput, devicePasswordInput, deviceIPInput, deviceIPGroup, deviceTypeSelect;
let devicePasswords = {}; // Object to store device passwords
let currentActionDevice = null; // Currently edited/deleted device
let currentActionType = null; // Action type ('edit' or 'delete')

/**
 * Device scanning and selection functionality
 */
function scanForDevices(method) {
    const deviceListContainer = document.querySelector('.device-list-container');
    
    // Add loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-indicator';
    loadingIndicator.innerHTML = `
        <div class="spinner"></div>
        <div class="loading-text">Skanowanie urządzeń...</div>
    `;
    deviceListContainer.innerHTML = '';
    deviceListContainer.appendChild(loadingIndicator);
    
    // Show device list
    document.getElementById('deviceList').style.display = 'block';
    
    // Make API request
    fetch(`${API_BASE_URL}/devices/scan?method=${method}`)
        .then(response => response.json())
        .then(data => {
            // Remove loading indicator
            deviceListContainer.removeChild(loadingIndicator);
            
            if (data.error) {
                // Display error
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-message';
                errorDiv.textContent = data.error;
                deviceListContainer.appendChild(errorDiv);
                return;
            }
            
            if (data.devices && data.devices.length > 0) {
                // Show found devices
                data.devices.forEach((device, index) => {
                    const deviceItem = document.createElement('div');
                    deviceItem.className = 'device-list-item';
                    deviceItem.setAttribute('data-id', device.id);
                    
                    const deviceIcon = device.type || getDeviceIconByName(device.name);
                    const deviceName = device.name || 'Nieznane urządzenie';
                    
                    // Add MAC address display
                    const addressDisplay = device.address ? 
                        `<div class="device-address">${device.address}</div>` : 
                        '<div class="device-address">Brak adresu MAC</div>';
                    
                    deviceItem.innerHTML = `
                        <div class="device-list-icon">${deviceIcon}</div>
                        <div class="device-list-info">
                            <div class="device-list-name">${deviceName}</div>
                            ${addressDisplay}
                        </div>
                    `;
                    
                    // Add click handler
                    deviceItem.addEventListener('click', function() {
                        // Remove previous selection
                        document.querySelectorAll('.device-list-item').forEach(item => {
                            item.classList.remove('selected');
                        });
                        
                        // Select this device
                        this.classList.add('selected');
                        
                        // Fill the form with device name
                        document.getElementById('deviceName').value = deviceName;
                        
                        // Set appropriate device type
                        const deviceTypeSelect = document.getElementById('deviceType');
                        const iconType = deviceIcon.trim();
                        
                        // Find option with matching icon
                        for (let i = 0; i < deviceTypeSelect.options.length; i++) {
                            if (deviceTypeSelect.options[i].value === iconType) {
                                deviceTypeSelect.selectedIndex = i;
                                break;
                            }
                        }
                        
                        // If device has IP address or is Bluetooth, fill IP/address field
                        if (device.address) {
                            document.getElementById('deviceIP').value = device.address;
                        } else if (method === 'wifi') {
                            // For WiFi networks we can simulate IP
                            document.getElementById('deviceIP').value = generateRandomIP();
                        }
                    });
                    
                    deviceListContainer.appendChild(deviceItem);
                });
            } else {
                // No devices found
                const noDevicesDiv = document.createElement('div');
                noDevicesDiv.className = 'no-devices-message';
                noDevicesDiv.textContent = 'Nie znaleziono żadnych urządzeń.';
                deviceListContainer.appendChild(noDevicesDiv);
            }
        })
        .catch(error => {
            console.error('Błąd podczas skanowania urządzeń:', error);
            
            // Remove loading indicator
            if (loadingIndicator.parentNode === deviceListContainer) {
                deviceListContainer.removeChild(loadingIndicator);
            }
            
            // Show error message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = 'Wystąpił błąd podczas łączenia z API. Sprawdź, czy serwer API jest uruchomiony.';
            deviceListContainer.appendChild(errorDiv);
        });
}

/**
 * Bluetooth device scanning with separate sections for paired and available devices
 */
function scanBluetoothDevices() {
    const deviceListContainer = document.querySelector('.device-list-container');
    
    // Add loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-indicator';
    loadingIndicator.innerHTML = `
        <div class="spinner"></div>
        <div class="loading-text">Scanning Bluetooth devices...</div>
    `;
    deviceListContainer.innerHTML = '';
    deviceListContainer.appendChild(loadingIndicator);
    
    // Show device list
    document.getElementById('deviceList').style.display = 'block';
    
    // Get two types of devices: paired and available
    Promise.all([
        fetch(`${API_BASE_URL}/devices/bluetooth`).then(response => response.json()),
        fetch(`${API_BASE_URL}/devices/bluetooth/paired`).then(response => response.json())
    ])
    .then(([availableData, pairedData]) => {
        // Remove loading indicator
        deviceListContainer.removeChild(loadingIndicator);
        
        // Check for errors
        if (availableData.error && pairedData.error) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = 'An error occurred while scanning Bluetooth devices.';
            deviceListContainer.appendChild(errorDiv);
            return;
        }
        
        // Prepare paired devices
        const pairedDevices = pairedData.devices || [];
        
        // Prepare available devices (not paired)
        const availableDevices = availableData.devices || [];
        
        // Device count
        const hasPaired = pairedDevices.length > 0;
        const hasAvailable = availableDevices.length > 0;
        
        // Create container for device lists
        const bluetoothContainer = document.createElement('div');
        bluetoothContainer.className = 'bluetooth-devices-container';
        
        // Add paired devices section
        if (hasPaired) {
            const pairedSection = document.createElement('div');
            pairedSection.className = 'bluetooth-section paired-devices';
            
            const sectionTitle = document.createElement('div');
            sectionTitle.className = 'bluetooth-section-title';
            sectionTitle.innerHTML = '📱 Paired devices';
            pairedSection.appendChild(sectionTitle);
            
            const pairedList = document.createElement('div');
            pairedList.className = 'bluetooth-device-list';
            
            pairedDevices.forEach((device) => {
                const deviceItem = createDeviceListItem(device, true);
                pairedList.appendChild(deviceItem);
            });
            
            pairedSection.appendChild(pairedList);
            bluetoothContainer.appendChild(pairedSection);
        }
        
        // Add available devices section
        if (hasAvailable) {
            const availableSection = document.createElement('div');
            availableSection.className = 'bluetooth-section available-devices';
            
            const sectionTitle = document.createElement('div');
            sectionTitle.className = 'bluetooth-section-title';
            sectionTitle.innerHTML = '🔍 Detected devices';
            availableSection.appendChild(sectionTitle);
            
            const availableList = document.createElement('div');
            availableList.className = 'bluetooth-device-list';
            
            availableDevices.forEach((device) => {
                const deviceItem = createDeviceListItem(device, false);
                availableList.appendChild(deviceItem);
            });
            
            availableSection.appendChild(availableList);
            bluetoothContainer.appendChild(availableSection);
        }
        
        // If no devices found
        if (!hasPaired && !hasAvailable) {
            const noDevicesDiv = document.createElement('div');
            noDevicesDiv.className = 'no-devices-message';
            noDevicesDiv.textContent = 'No Bluetooth devices found.';
            bluetoothContainer.appendChild(noDevicesDiv);
        }
        
        // Add everything to device container
        deviceListContainer.appendChild(bluetoothContainer);
    })
    .catch(error => {
        console.error('Error while scanning Bluetooth devices:', error);
        
        // Remove loading indicator
        if (loadingIndicator.parentNode === deviceListContainer) {
            deviceListContainer.removeChild(loadingIndicator);
        }
        
        // Show error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = 'An error occurred while connecting to the API. Check if the API server is running.';
        deviceListContainer.appendChild(errorDiv);
    });
}

/**
 * Helper function to create a device list item
 */
function createDeviceListItem(device, isPaired) {
    const deviceItem = document.createElement('div');
    deviceItem.className = 'device-list-item';
    if (isPaired) deviceItem.classList.add('paired-device');
    deviceItem.setAttribute('data-id', device.id);
    
    const deviceIcon = device.type || getDeviceIconByName(device.name);
    const deviceName = device.name || 'Nieznane urządzenie';
    
    // Add badge for paired devices
    const pairedBadge = isPaired ? '<span class="paired-badge">✓</span>' : '';
    
    // Always show MAC address, even if not available
    const macAddress = device.address || 'Brak adresu MAC';
    
    deviceItem.innerHTML = `
        <div class="device-list-icon">${deviceIcon}</div>
        <div class="device-list-info">
            <div class="device-list-name">${deviceName} ${pairedBadge}</div>
            <div class="device-address">${macAddress}</div>
        </div>
    `;
    
    // Add click handler
    deviceItem.addEventListener('click', function() {
        // Remove previous selection
        document.querySelectorAll('.device-list-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Select this device
        this.classList.add('selected');
        
        // Fill the form with device name
        document.getElementById('deviceName').value = deviceName;
        
        // Set appropriate device type
        const deviceTypeSelect = document.getElementById('deviceType');
        const iconType = deviceIcon.trim();
        
        // Find option with matching icon
        for (let i = 0; i < deviceTypeSelect.options.length; i++) {
            if (deviceTypeSelect.options[i].value === iconType) {
                deviceTypeSelect.selectedIndex = i;
                break;
            }
        }
        
        // If device has address, fill address field
        if (device.address && device.address !== "Sparowane urządzenie" && 
            device.address !== "Nieznany adres" && device.address !== "Brak sparowanych urządzeń") {
            document.getElementById('deviceIP').value = device.address;
        }
    });
    
    return deviceItem;
}

/**
 * Helper functions
 */
// Generate random IP address
function generateRandomIP() {
    return `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`;
}

// Get device icon based on device name
function getDeviceIconByName(name) {
    if (!name) return '📱';
    
    name = name.toLowerCase();
    
    if (name.includes('phone') || name.includes('iphone') || name.includes('samsung') || name.includes('xiaomi')) {
        return '📱';
    } else if (name.includes('laptop') || name.includes('notebook') || name.includes('macbook')) {
        return '💻';
    } else if (name.includes('printer') || name.includes('drukarka')) {
        return '🖨️';
    } else if (name.includes('computer') || name.includes('desktop') || name.includes('pc')) {
        return '🖥️';
    } else if (name.includes('camera') || name.includes('kamera')) {
        return '📹';
    } else if (name.includes('socket') || name.includes('plug') || name.includes('gniazdko')) {
        return '🔌';
    } else if (name.includes('sensor') || name.includes('czujnik')) {
        return '🌡️';
    } else {
        return '📱'; // Default icon
    }
}

// Generate unique ID for devices
function generateUniqueId() {
    return 'DEV_' + Math.floor(Math.random() * 10000).toString().padStart(4, '0') + '_' + 
           Math.floor(Math.random() * 10000).toString().padStart(4, '0');
}

/**
 * UI manipulation functions
 */
// Toggle sidebar visibility
function toggleSidebar() {
    if (IS_MOBILE) {
        sidebar.classList.toggle('expanded');
    } else {
        const isCollapsed = sidebar.classList.contains('collapsed');
        sidebar.classList.toggle('collapsed');
        mainContent.classList.toggle('expanded');
        
        // Toggle external button visibility with delay
        if (isCollapsed) {
            // Sidebar was collapsed, now will be expanded
            // Hide button immediately
            toggleButtonExternal.style.display = 'none';
        } else {
            // Sidebar was expanded, now will be collapsed
            // Show button with delay
            setTimeout(function() {
                toggleButtonExternal.style.display = 'flex';
            }, 250);
        }
    }
}

// Initialize device sections in sidebar
function initDeviceSections() {
    // Remove existing sections if they exist
    const existingFavorites = document.querySelector('.sidebar-category.favorite-devices');
    const existingOnline = document.querySelector('.sidebar-category.online-devices');
    const existingOffline = document.querySelector('.sidebar-category.offline-devices');
    
    if (existingFavorites) existingFavorites.remove();
    if (existingOnline) existingOnline.remove();
    if (existingOffline) existingOffline.remove();
    
    // Create section for favorite devices
    const favoritesSection = document.createElement('div');
    favoritesSection.className = 'sidebar-category favorite-devices';
    favoritesSection.textContent = 'Favorites';
    
    // Create section for online devices
    const onlineSection = document.createElement('div');
    onlineSection.className = 'sidebar-category online-devices';
    onlineSection.textContent = 'Available devices';
    
    // Create section for offline devices
    const offlineSection = document.createElement('div');
    offlineSection.className = 'sidebar-category offline-devices';
    offlineSection.textContent = 'Offline devices';
    
    // Insert sections after filters element
    const filtersSection = document.querySelector('.filters-section');
    
    // Insert sections in order
    sidebar.insertBefore(favoritesSection, filtersSection.nextSibling);
    sidebar.insertBefore(onlineSection, favoritesSection.nextSibling);
    sidebar.insertBefore(offlineSection, onlineSection.nextSibling);
    
    // Initially display all sections
    favoritesSection.style.display = 'block';
    onlineSection.style.display = 'block';
    offlineSection.style.display = 'block';
}

// Initialize filter functionality
function initFilters() {
    const filtersToggle = document.getElementById('filtersToggle');
    const filtersContent = document.getElementById('filtersContent');
    const filterAvailable = document.getElementById('filterAvailable');
    const filterOffline = document.getElementById('filterOffline');
    const deviceTypeFilter = document.getElementById('deviceTypeFilter');
    const clearFiltersBtn = document.getElementById('clearFilters');
    
    // Toggle filters panel visibility
    filtersToggle.addEventListener('click', function() {
        if (filtersContent.style.display === 'none') {
            filtersContent.style.display = 'block';
            filtersToggle.classList.add('expanded');
        } else {
            filtersContent.style.display = 'none';
            filtersToggle.classList.remove('expanded');
        }
    });
    
    // Handle filter changes
    filterAvailable.addEventListener('change', applyFilters);
    filterOffline.addEventListener('change', applyFilters);
    deviceTypeFilter.addEventListener('change', applyFilters);
    
    // Handle clear filters button
    clearFiltersBtn.addEventListener('click', function() {
        filterAvailable.checked = true;
        filterOffline.checked = true;
        deviceTypeFilter.value = 'all';
        applyFilters();
    });
    
    // Apply initial filters
    applyFilters();
}

// Apply filters to devices
function applyFilters() {
    const filterAvailable = document.getElementById('filterAvailable');
    const filterOffline = document.getElementById('filterOffline');
    const deviceTypeFilter = document.getElementById('deviceTypeFilter');
    const showAvailable = filterAvailable.checked;
    const showOffline = filterOffline.checked;
    const selectedDeviceType = deviceTypeFilter.value;
    
    const devices = document.querySelectorAll('.sidebar-link');
    
    // Flag for favorites only
    let hasFavorites = false;
    
    devices.forEach(device => {
        const deviceStatus = device.getAttribute('data-status');
        const deviceType = device.getAttribute('data-device-type');
        const isFavorite = device.getAttribute('data-favorite') === 'true';
        let shouldShow = true;
        
        // Check device status
        if ((deviceStatus === 'online' && !showAvailable) || 
            (deviceStatus === 'offline' && !showOffline)) {
            shouldShow = false;
        }
        
        // Check device type
        if (selectedDeviceType !== 'all' && deviceType !== selectedDeviceType) {
            shouldShow = false;
        }
        
        // Apply filter
        if (shouldShow) {
            device.classList.remove('filtered');
            
            // Update only favorites flag
            if (isFavorite) {
                hasFavorites = true;
            }
        } else {
            device.classList.add('filtered');
        }
    });
    
    // Update section visibility - only favorites depends on content
    const favoritesSection = document.querySelector('.sidebar-category.favorite-devices');
    const onlineSection = document.querySelector('.sidebar-category.online-devices');
    const offlineSection = document.querySelector('.sidebar-category.offline-devices');
    
    if (favoritesSection) {
        favoritesSection.style.display = hasFavorites ? 'block' : 'none';
    }
    
    // Online and offline sections are always visible
    if (onlineSection) {
        onlineSection.style.display = 'block';
    }
    
    if (offlineSection) {
        offlineSection.style.display = 'block';
    }
}

// Update visibility of sections based on content
function updateSectionVisibility() {
    // Check if any devices are visible in sections
    const hasFavorites = document.querySelectorAll('.sidebar-link[data-favorite="true"]:not(.filtered)').length > 0;
    
    // Update section visibility
    const favoritesSection = document.querySelector('.sidebar-category.favorite-devices');
    
    // Favorites section depends on content
    if (favoritesSection) {
        favoritesSection.style.display = hasFavorites ? 'block' : 'none';
    }
}

// Check if device should be filtered based on current filters
function shouldBeFiltered(deviceElement) {
    const filterAvailable = document.getElementById('filterAvailable');
    const filterOffline = document.getElementById('filterOffline');
    const deviceTypeFilter = document.getElementById('deviceTypeFilter');
    const deviceStatus = deviceElement.getAttribute('data-status');
    const deviceType = deviceElement.getAttribute('data-device-type');
    const showAvailable = filterAvailable.checked;
    const showOffline = filterOffline.checked;
    const selectedDeviceType = deviceTypeFilter.value;
    
    // Check device status
    if ((deviceStatus === 'online' && !showAvailable) || 
        (deviceStatus === 'offline' && !showOffline)) {
        return true;
    }
    
    // Check device type
    if (selectedDeviceType !== 'all' && deviceType !== selectedDeviceType) {
        return true;
    }
    
    return false;
}

/**
 * Device management functions
 */
// Add new device to sidebar
function addDeviceToSidebar(name, id, isProtected, deviceType, deviceIP, isManuallyAdded) {
    // Create new device element
    const newDevice = document.createElement('div');
    newDevice.className = 'sidebar-link';
    
    // Random status for device (demo)
    const statuses = ['online', 'offline'];
    const randomStatus = statuses[Math.floor(Math.random() * statuses.length)];
    
    // Device structure with star and action buttons
    newDevice.innerHTML = `
        <div class="device-name">
            <span class="device-status status-${randomStatus}"></span>
            <span class="favorite-star">☆</span>
            <span class="device-type-icon">${deviceType}</span>
            ${name} ${isProtected ? '<span style="margin-left: 5px; font-size: 12px;">🔒</span>' : ''}
        </div>
        <div class="device-actions">
            <button class="device-action-btn edit-device" title="Edit device">✏️</button>
            <button class="device-action-btn delete-device" title="Delete device">🗑️</button>
        </div>
    `;
    
    // Add data attributes
    newDevice.setAttribute('data-device-id', id);
    newDevice.setAttribute('data-protected', isProtected ? 'true' : 'false');
    newDevice.setAttribute('data-status', randomStatus);
    newDevice.setAttribute('data-favorite', 'false');
    newDevice.setAttribute('data-device-type', deviceType);
    
    // Add IP address as data attribute if it exists
    if (deviceIP) {
        newDevice.setAttribute('data-ip', deviceIP);
    }
    
    // Add information if device was manually added
    newDevice.setAttribute('data-manual-add', isManuallyAdded ? 'true' : 'false');
    
    // Add device to appropriate section
    if (randomStatus === 'online') {
        const onlineSection = document.querySelector('.sidebar-category.online-devices');
        sidebar.insertBefore(newDevice, onlineSection.nextSibling);
    } else {
        const offlineSection = document.querySelector('.sidebar-category.offline-devices');
        sidebar.insertBefore(newDevice, offlineSection.nextSibling);
    }
    
    // Add event handlers for action buttons
    const editButton = newDevice.querySelector('.edit-device');
    const deleteButton = newDevice.querySelector('.delete-device');
    const favoriteButton = newDevice.querySelector('.favorite-star');
    
    editButton.addEventListener('click', function(e) {
        e.stopPropagation(); // Stop propagation
        handleDeviceAction(newDevice, 'edit');
    });
    
    deleteButton.addEventListener('click', function(e) {
        e.stopPropagation(); // Stop propagation
        handleDeviceAction(newDevice, 'delete');
    });
    
    // Handle favorite star click
    favoriteButton.addEventListener('click', function(e) {
        e.stopPropagation(); // Stop propagation
        toggleFavorite(newDevice);
    });
    
    // Open sidebar if it's closed
    if (sidebar.classList.contains('collapsed')) {
        toggleSidebar();
    }
}

// Update device in sidebar
function updateDeviceInSidebar(deviceElement, name, id, isProtected, deviceType, deviceIP, isManuallyAdded) {
    const deviceNameElement = deviceElement.querySelector('.device-name');
    const currentStatus = deviceElement.getAttribute('data-status');
    const isFavorite = deviceElement.getAttribute('data-favorite') === 'true';
    const favoriteIcon = isFavorite ? '★' : '☆';
    const favoriteClass = isFavorite ? 'active' : '';
    
    // Update device type attribute
    deviceElement.setAttribute('data-device-type', deviceType);
    
    // Save IP address as data attribute if it exists
    if (deviceIP) {
        deviceElement.setAttribute('data-ip', deviceIP);
    } else {
        deviceElement.removeAttribute('data-ip');
    }
    
    // Keep information if device was manually added
    if (typeof isManuallyAdded !== 'undefined') {
        deviceElement.setAttribute('data-manual-add', isManuallyAdded ? 'true' : 'false');
    }
    
    deviceNameElement.innerHTML = `
        <span class="device-status status-${currentStatus}"></span>
        <span class="favorite-star ${favoriteClass}">${favoriteIcon}</span>
        <span class="device-type-icon">${deviceType}</span>
        ${name} ${isProtected ? '<span style="margin-left: 5px; font-size: 12px;">🔒</span>' : ''}
    `;
    deviceElement.setAttribute('data-protected', isProtected ? 'true' : 'false');
    
    // Add favorite star click handler again (since HTML was overwritten)
    const newFavoriteButton = deviceElement.querySelector('.favorite-star');
    newFavoriteButton.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleFavorite(deviceElement);
    });
    
    // Move device to appropriate section
    moveDeviceToCorrectSection(deviceElement);
}

// Delete device from sidebar
function deleteDevice(deviceElement) {
    // Remove password from memory
    const deviceId = deviceElement.getAttribute('data-device-id');
    delete devicePasswords[deviceId];
    
    // Remove element from DOM
    deviceElement.parentNode.removeChild(deviceElement);
}

// Handle device actions (edit/delete)
function handleDeviceAction(deviceElement, actionType) {
    currentActionDevice = deviceElement;
    currentActionType = actionType;
    
    const isProtected = deviceElement.getAttribute('data-protected') === 'true';
    
    // If device is password protected, verify password first
    if (isProtected) {
        const passwordPromptText = document.getElementById('passwordPromptText');
        
        // Set appropriate text for action
        if (actionType === 'edit') {
            passwordPromptText.textContent = "Enter password to edit device.";
        } else if (actionType === 'delete') {
            passwordPromptText.textContent = "Enter password to delete device.";
        }
        
        // Show password verification modal
        passwordVerifyModal.classList.add('show');
    } else {
        // If device is not protected, perform action immediately
        if (actionType === 'edit') {
            openEditDeviceModal(deviceElement);
        } else if (actionType === 'delete') {
            if (confirm('Are you sure you want to delete this device?')) {
                deleteDevice(deviceElement);
                // After deleting device, update section visibility
                updateSectionVisibility();
            }
        }
    }
}

// Open edit device modal
function openEditDeviceModal(deviceElement) {
    const editDeviceNameInput = document.getElementById('editDeviceName');
    const editDeviceIdInput = document.getElementById('editDeviceId');
    const editPasswordProtectCheckbox = document.getElementById('editPasswordProtect');
    const editPasswordGroup = document.getElementById('editPasswordGroup');
    const editDevicePasswordInput = document.getElementById('editDevicePassword');
    const editDeviceTypeSelect = document.getElementById('editDeviceType');
    
    // Get device name HTML content
    const deviceNameHTML = deviceElement.querySelector('.device-name').innerHTML;
    
    // Use more reliable approach to extract name
    // Remove all span tags and their content
    let cleanName = deviceNameHTML.replace(/<span[^>]*>.*?<\/span>/g, '');
    
    // Remove extra spaces and trim
    cleanName = cleanName.replace(/\s+/g, ' ').trim();
    
    const deviceId = deviceElement.getAttribute('data-device-id');
    const isProtected = deviceElement.getAttribute('data-protected') === 'true';
    const deviceType = deviceElement.getAttribute('data-device-type');
    
    // Get device IP address and information if it was manually added
    const deviceIP = deviceElement.getAttribute('data-ip') || '';
    const isManuallyAdded = deviceElement.getAttribute('data-manual-add') === 'true';
    
    // Fill edit form
    editDeviceNameInput.value = cleanName;
    editDeviceIdInput.value = deviceId;
    editPasswordProtectCheckbox.checked = isProtected;
    editDeviceTypeSelect.value = deviceType;
    
    // If IP edit element exists, fill it with IP address
    const editDeviceIPInput = document.getElementById('editDeviceIP');
    const editDeviceIPGroup = document.getElementById('editDeviceIPGroup');
    
    if (editDeviceIPInput && editDeviceIPGroup) {
        editDeviceIPInput.value = deviceIP;
        
        // Show IP field for all devices
        editDeviceIPGroup.style.display = 'block';
        
        // But disable editing for devices that were not manually added
        if (isManuallyAdded) {
            editDeviceIPInput.disabled = false;
            editDeviceIPInput.classList.remove('disabled-input');
        } else {
            editDeviceIPInput.disabled = true;
            editDeviceIPInput.classList.add('disabled-input');
            
            // Clear IP field if device was not manually added and has no IP
            if (!deviceIP) {
                editDeviceIPInput.value = 'Not available for this connection type';
            }
        }
    }
    
    // Show/hide password field
    editPasswordGroup.style.display = isProtected ? 'block' : 'none';
    editDevicePasswordInput.value = ''; // Clear password field
    
    // Show modal
    editDeviceModal.classList.add('show');
}

// Toggle favorite status
function toggleFavorite(deviceElement) {
    const isFavorite = deviceElement.getAttribute('data-favorite') === 'true';
    const favoriteIcon = deviceElement.querySelector('.favorite-star');
    
    if (isFavorite) {
        // Remove from favorites
        deviceElement.setAttribute('data-favorite', 'false');
        favoriteIcon.textContent = '☆'; // Empty star
        favoriteIcon.classList.remove('active');
        
        // Move device to appropriate section based on status
        moveDeviceToCorrectSection(deviceElement);
    } else {
        // Add to favorites
        deviceElement.setAttribute('data-favorite', 'true');
        favoriteIcon.textContent = '★'; // Filled star
        favoriteIcon.classList.add('active');
        
        // Move device to favorites section
        moveDeviceToFavorites(deviceElement);
        
        // Add pulse effect
        deviceElement.classList.add('just-favorited');
        setTimeout(() => {
            deviceElement.classList.remove('just-favorited');
        }, 1000);
    }
    
    // After changing favorite status, update section visibility
    updateSectionVisibility();
}

// Move device to favorites section
function moveDeviceToFavorites(deviceElement) {
    const favoritesSection = document.querySelector('.sidebar-category.favorite-devices');
    
    if (favoritesSection) {
        // Move device to top of favorites section
        sidebar.insertBefore(deviceElement, favoritesSection.nextSibling);
    }
}

// Toggle device status (for demo)
function toggleDeviceStatus(deviceElement) {
    const currentStatus = deviceElement.getAttribute('data-status');
    const newStatus = currentStatus === 'online' ? 'offline' : 'online';
    
    // Update status
    deviceElement.setAttribute('data-status', newStatus);
    
    // Update status icon
    const statusIcon = deviceElement.querySelector('.device-status');
    statusIcon.className = `device-status status-${newStatus}`;
    
    // Move to appropriate section
    moveDeviceToCorrectSection(deviceElement);
    
    // After changing status, update section visibility
    updateSectionVisibility();
}

// Move device to appropriate section
function moveDeviceToCorrectSection(deviceElement) {
    const status = deviceElement.getAttribute('data-status');
    const isFavorite = deviceElement.getAttribute('data-favorite') === 'true';
    
    if (isFavorite) {
        // If favorite, move to favorites section
        moveDeviceToFavorites(deviceElement);
    } else {
        // Otherwise move according to status
        if (status === 'online') {
            const onlineSection = document.querySelector('.sidebar-category.online-devices');
            sidebar.insertBefore(deviceElement, onlineSection.nextSibling);
        } else {
            const offlineSection = document.querySelector('.sidebar-category.offline-devices');
            sidebar.insertBefore(deviceElement, offlineSection.nextSibling);
        }
    }
}

// Ensure matching sections are visible
function ensureMatchingSectionsVisible() {
    // Check which sections have found devices
    const hasFavoriteMatches = document.querySelectorAll('.sidebar-link[data-favorite="true"].search-match').length > 0;
    
    // Update section visibility
    const favoritesSection = document.querySelector('.sidebar-category.favorite-devices');
    
    if (favoritesSection) {
        favoritesSection.style.display = hasFavoriteMatches ? 'block' : 'none';
    }
}



// Close modal
function closeModal(modal) {
    modal.classList.remove('show');
}

/**
 * Search functionality
 */
// Add animation pulse effect
function addAnimationPulse(element) {
    element.style.animation = 'searchPulse 2s infinite';
    element.style.backgroundColor = '#3a3b45';
}

// Remove all animation effects
function removeAllAnimationEffects(element) {
    // Remove animation
    element.style.animation = 'none';
    
    // Reset background
    element.style.backgroundColor = 'transparent';
    
    // Add animation-stopped class
    element.classList.add('animation-stopped');
}

/**
 * Document ready event handler
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize DOM elements
    sidebar = document.getElementById('sidebar');
    mainContent = document.getElementById('mainContent');
    toggleButtonExternal = document.getElementById('toggleSidebarExternal');
    toggleButtonInside = document.getElementById('toggleSidebarInside');
    
    // Add modals
    addDeviceModal = document.getElementById('addDeviceModal');
    passwordVerifyModal = document.getElementById('passwordVerifyModal');
    editDeviceModal = document.getElementById('editDeviceModal');
    
    // Form elements
    deviceNameInput = document.getElementById('deviceName');
    deviceIdInput = document.getElementById('deviceId');
    devicePasswordInput = document.getElementById('devicePassword');
    deviceIPInput = document.getElementById('deviceIP');
    deviceIPGroup = document.getElementById('deviceIPGroup');
    deviceTypeSelect = document.getElementById('deviceType');
    
    // Sidebar is initially collapsed (regardless of device)
    sidebar.classList.add('collapsed');
    mainContent.classList.add('expanded');
    toggleButtonExternal.style.display = 'flex'; // Show external button
    
    // Initialize device sections and filters
    initDeviceSections();
    initFilters();
    
    // Toggle sidebar button handlers
    toggleButtonInside.addEventListener('click', toggleSidebar);
    toggleButtonExternal.addEventListener('click', toggleSidebar);
    
    // Window resize handler
    window.addEventListener('resize', function() {
        const newIsMobile = window.innerWidth <= 768;
        if (newIsMobile !== IS_MOBILE) {
            location.reload(); // Reload page when device type changes
        }
    });
    
    // Add device button click
    const addDeviceButton = document.getElementById('addDeviceButton');
    addDeviceButton.addEventListener('click', function() {
        // Generate unique ID for new device
        deviceIdInput.value = generateUniqueId();
        
        // Reset form
        deviceNameInput.value = '';
        const passwordProtectCheckbox = document.getElementById('passwordProtect');
        const passwordGroup = document.getElementById('passwordGroup');
        passwordProtectCheckbox.checked = false;
        passwordGroup.style.display = 'none';
        devicePasswordInput.value = '';
        deviceIPInput.value = '';
        deviceIPGroup.style.display = 'none'; // Hide IP field initially
        deviceTypeSelect.value = deviceTypeSelect.options[0].value; // Default value
        
        // Reset connection method choices
        const connectionOptions = document.querySelectorAll('.connection-option');
        connectionOptions.forEach(opt => opt.classList.remove('selected'));
        document.getElementById('deviceList').style.display = 'none';
        
        // Show modal
        addDeviceModal.classList.add('show');
    });
    
    // Password protection checkbox handlers
    const passwordProtectCheckbox = document.getElementById('passwordProtect');
    const passwordGroup = document.getElementById('passwordGroup');
    passwordProtectCheckbox.addEventListener('change', function() {
        passwordGroup.style.display = this.checked ? 'block' : 'none';
        if (this.checked) {
            devicePasswordInput.setAttribute('required', 'required');
        } else {
            devicePasswordInput.removeAttribute('required');
        }
    });
    
    const editPasswordProtectCheckbox = document.getElementById('editPasswordProtect');
    const editPasswordGroup = document.getElementById('editPasswordGroup');
    editPasswordProtectCheckbox.addEventListener('change', function() {
        editPasswordGroup.style.display = this.checked ? 'block' : 'none';
        if (this.checked) {
            document.getElementById('editDevicePassword').setAttribute('required', 'required');
        } else {
            document.getElementById('editDevicePassword').removeAttribute('required');
        }
    });
    
    // Device click handler (toggles status - demo only)
    sidebar.addEventListener('click', function(event) {
        const deviceElement = event.target.closest('.sidebar-link');
        if (deviceElement && !event.target.closest('.device-actions') && !event.target.closest('.favorite-star')) {
            toggleDeviceStatus(deviceElement);
        }
    });
    
    // Confirm add device button
    const confirmAddDeviceBtn = document.getElementById('confirmAddDevice');
    confirmAddDeviceBtn.addEventListener('click', function() {
        const deviceName = deviceNameInput.value.trim();
        const deviceId = deviceIdInput.value;
        const isPasswordProtected = passwordProtectCheckbox.checked;
        const password = devicePasswordInput.value;
        const deviceType = deviceTypeSelect.value;
        
        // Check if "Manual" option is selected
        const manualOptionSelected = document.querySelector('.connection-option[data-method="manual"].selected');
        const deviceIP = deviceIPInput.value.trim();
        
        // Validation
        if (!deviceName) {
            alert('Enter device name!');
            return;
        }
        
        if (isPasswordProtected && !password) {
            alert('Enter password for protected device!');
            return;
        }
        
        // Check if "Manual" option is selected and IP entered
        if (manualOptionSelected && !deviceIP) {
            alert('Enter device IP!');
            return;
        }
        
        // Save password if protected
        if (isPasswordProtected) {
            devicePasswords[deviceId] = password;
        }
        
        // Add device to sidebar with specified type and IP (if exists)
        addDeviceToSidebar(deviceName, deviceId, isPasswordProtected, deviceType, manualOptionSelected ? deviceIP : '', manualOptionSelected);
        
        // Close modal
        closeModal(addDeviceModal);
        
        // Update section visibility
        updateSectionVisibility();
    });
    
    // Confirm password verification
    const confirmPasswordVerifyBtn = document.getElementById('confirmPasswordVerify');
    confirmPasswordVerifyBtn.addEventListener('click', function() {
        const enteredPassword = document.getElementById('verifyPassword').value;
        const deviceId = currentActionDevice.getAttribute('data-device-id');
        const correctPassword = devicePasswords[deviceId];
        
        if (enteredPassword === correctPassword) {
            // Password correct - perform action
            closeModal(passwordVerifyModal);
            
            if (currentActionType === 'edit') {
                openEditDeviceModal(currentActionDevice);
            } else if (currentActionType === 'delete') {
                deleteDevice(currentActionDevice);
                // After deleting device, update section visibility
                updateSectionVisibility();
            }
        } else {
            alert('Incorrect password!');
        }
        
        // Reset password field
        document.getElementById('verifyPassword').value = '';
    });
    
    // Save edit changes
    const confirmEditDeviceBtn = document.getElementById('confirmEditDevice');
    confirmEditDeviceBtn.addEventListener('click', function() {
        const editDeviceNameInput = document.getElementById('editDeviceName');
        const editDeviceIdInput = document.getElementById('editDeviceId');
        const editPasswordProtectCheckbox = document.getElementById('editPasswordProtect');
        const editDevicePasswordInput = document.getElementById('editDevicePassword');
        const editDeviceTypeSelect = document.getElementById('editDeviceType');
        
        const deviceName = editDeviceNameInput.value.trim();
        const deviceId = editDeviceIdInput.value;
        const isPasswordProtected = editPasswordProtectCheckbox.checked;
        const password = editDevicePasswordInput.value;
        const deviceType = editDeviceTypeSelect.value;
        
        // Get IP from form if field exists
        const editDeviceIPInput = document.getElementById('editDeviceIP');
        // Get IP only if field is not disabled
        const deviceIP = (editDeviceIPInput && !editDeviceIPInput.disabled) ? 
            editDeviceIPInput.value.trim() : currentActionDevice.getAttribute('data-ip') || '';
        
        // Validation
        if (!deviceName) {
            alert('Enter device name!');
            return;
        }
        
        if (isPasswordProtected && !password && !devicePasswords[deviceId]) {
            alert('Enter password for protected device!');
            return;
        }
        
        // Check if device was manually added and IP entered
        const isManuallyAdded = currentActionDevice.getAttribute('data-manual-add') === 'true';
        if (isManuallyAdded && !deviceIP) {
            alert('Enter device IP!');
            return;
        }
        
        // Update password if protected and password changed
        if (isPasswordProtected) {
            if (password) {
                devicePasswords[deviceId] = password;
            }
        } else {
            // Remove password if protection deactivated
            delete devicePasswords[deviceId];
        }
        
        // Update element in list
        updateDeviceInSidebar(currentActionDevice, deviceName, deviceId, isPasswordProtected, deviceType, deviceIP, isManuallyAdded);
        
        // Close modal
        closeModal(editDeviceModal);
        
        // Update section visibility
        updateSectionVisibility();
    });
    
    // Modal close buttons
    const closeModalBtn = document.getElementById('closeModal');
    const cancelAddDeviceBtn = document.getElementById('cancelAddDevice');
    closeModalBtn.addEventListener('click', function() { closeModal(addDeviceModal); });
    cancelAddDeviceBtn.addEventListener('click', function() { closeModal(addDeviceModal); });
    
    const closePasswordModalBtn = document.getElementById('closePasswordModal');
    const cancelPasswordVerifyBtn = document.getElementById('cancelPasswordVerify');
    closePasswordModalBtn.addEventListener('click', function() { closeModal(passwordVerifyModal); });
    cancelPasswordVerifyBtn.addEventListener('click', function() { closeModal(passwordVerifyModal); });
    
    const closeEditModalBtn = document.getElementById('closeEditModal');
    const cancelEditDeviceBtn = document.getElementById('cancelEditDevice');
    closeEditModalBtn.addEventListener('click', function() { closeModal(editDeviceModal); });
    cancelEditDeviceBtn.addEventListener('click', function() { closeModal(editDeviceModal); });
    
    // Connection options selection
    const connectionOptions = document.querySelectorAll('.connection-option');
    connectionOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Remove selected class from all options
            connectionOptions.forEach(opt => opt.classList.remove('selected'));
            
            // Add selected class to chosen option
            this.classList.add('selected');
            
            const method = this.getAttribute('data-method');
            
            // Depending on selected method
            if (method === 'wifi') {
                // Scan Wi-Fi networks
                scanForDevices('wifi');
                deviceIPGroup.style.display = 'block'; // Show IP field
            } else if (method === 'bluetooth') {
                // Scan Bluetooth devices
                scanForDevices('bluetooth');
                deviceIPGroup.style.display = 'none'; // Hide IP field
            } else if (method === 'camera') {
                // Scan cameras
                scanForDevices('camera');
                deviceIPGroup.style.display = 'none'; // Hide IP field
            } else if (method === 'manual') {
                // Manual method selected
                document.getElementById('deviceList').style.display = 'none';
                deviceIPGroup.style.display = 'block'; // Show IP field
                
                // If manual method selected, focus IP field
                setTimeout(() => {
                    deviceIPInput.focus();
                }, 100);
            } else {
                document.getElementById('deviceList').style.display = 'none';
                deviceIPGroup.style.display = 'none'; // Hide IP field
            }
        });
    });
    
    // Search button handler
    const searchButton = document.getElementById('searchButton');
    searchButton.addEventListener('click', function() {
        const searchQuery = prompt('Search device:');
        if (searchQuery && searchQuery.trim() !== '') {
            // Make sure we have search pulse keyframes defined
            if (!document.getElementById('search-pulse-keyframes')) {
                const keyframesStyle = document.createElement('style');
                keyframesStyle.id = 'search-pulse-keyframes';
                keyframesStyle.textContent = `
                    @keyframes searchPulse {
                        0% { background-color: #3a3b45; }
                        50% { background-color: rgba(77, 124, 254, 0.3); }
                        100% { background-color: #3a3b45; }
                    }
                `;
                document.head.appendChild(keyframesStyle);
            }
            
            // Search for matching elements
            const deviceLinks = document.querySelectorAll('.sidebar-link');
            let found = false;
            
            // Reset animations only, keep functionality
            deviceLinks.forEach(link => {
                // Remove animation styles
                link.style.animation = 'none';
                link.style.backgroundColor = 'transparent';
                
                // Remove animation-stopped class
                link.classList.remove('animation-stopped');
                
                // Remove search-match class
                link.classList.remove('search-match');
            });
            
            // Perform new search
            document.querySelectorAll('.sidebar-link').forEach(link => {
                const deviceName = link.querySelector('.device-name');
                
                if (deviceName && deviceName.textContent.toLowerCase().includes(searchQuery.toLowerCase())) {
                    // Mark found device
                    link.classList.add('search-match');
                    found = true;
                    
                    // Temporarily remove 'filtered' class that hides device
                    link.classList.remove('filtered');
                    
                    // Add pulse animation
                    addAnimationPulse(link);
                    
                    // Clear old mouseenter listeners
                    const oldListeners = link.getAttribute('data-has-search-listener');
                    
                    // Add mouseenter event handler - on hover remove visual effects only
                    link.addEventListener('mouseenter', function() {
                        if (!this.classList.contains('animation-stopped')) {
                            removeAllAnimationEffects(this);
                        }
                    });
                    
                    // Mark that element has listener
                    link.setAttribute('data-has-search-listener', 'true');
                }
            });
            
            if (!found) {
                alert('No devices found matching query: ' + searchQuery);
            } else {
                // Open sidebar if collapsed
                if (sidebar.classList.contains('collapsed')) {
                    toggleSidebar();
                }
                
                // Make sure sections are properly visible
                ensureMatchingSectionsVisible();
            }
        }
    });
    
    // Close modals by clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === addDeviceModal) {
            closeModal(addDeviceModal);
        }
        if (event.target === passwordVerifyModal) {
            closeModal(passwordVerifyModal);
        }
        if (event.target === editDeviceModal) {
            closeModal(editDeviceModal);
        }
    });

    // Add CSS styles for loader
    const style = document.createElement('style');
    style.textContent = `
        .loading-indicator {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border-left-color: #4D7CFE;
            animation: spin 1s linear infinite;
            margin-bottom: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .loading-text {
            color: #7A8CB1;
            font-size: 14px;
        }
        
        .error-message {
            color: #F44336;
            padding: 10px;
            text-align: center;
            border: 1px solid #F44336;
            border-radius: 4px;
            margin: 10px 0;
        }
        
        .no-devices-message {
            color: #7A8CB1;
            padding: 15px;
            text-align: center;
            border: 1px dashed #3D4A69;
            border-radius: 4px;
            margin: 10px 0;
        }
    `;
    document.head.appendChild(style);
});