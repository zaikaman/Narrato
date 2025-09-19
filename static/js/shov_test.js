const resultEl = document.getElementById('result');

async function apiCall(endpoint, body) {
    resultEl.textContent = 'Loading...';
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        resultEl.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        resultEl.textContent = `Error: ${error.message}`;
    }
}

function testSet() {
    const key = document.getElementById('sg-key').value;
    const value = document.getElementById('sg-value').value;
    apiCall('/api/shov/set', { key, value });
}

function testGet() {
    const key = document.getElementById('sg-key').value;
    apiCall('/api/shov/get', { key });
}

function testAdd() {
    const collection = document.getElementById('c-name').value;
    const value = document.getElementById('c-value').value;
    apiCall('/api/shov/add', { collection, value });
}

function testWhere() {
    const collection = document.getElementById('c-name').value;
    const filter = document.getElementById('c-filter').value;
    apiCall('/api/shov/where', { collection, filter });
}

function testRemove() {
    const collection = document.getElementById('c-name').value;
    const item_id = document.getElementById('c-remove-id').value;
    apiCall('/api/shov/remove', { collection, item_id });
}
