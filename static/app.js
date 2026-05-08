var socket = io({
    transports: ["websocket"],
    upgrade: false,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500, 
    reconnectionDelayMax: 3000,
    timeout: 10000 
});
var historyChart = null;
var latestRecords = [];
var maxRecordCount = 100; // Son 400 kaydı tut (yaklaşık 1 saat)
var hasSocketLiveUpdate = false;
var isInitialResetDone = false;
var A_REF = -53.5;
var N_VAL = 2.8;
let renderLock = false;

function scheduleRender() {
    if (renderLock) return;

    renderLock = true;

    setTimeout(() => {

        const last = latestRecords.at(-1);

        updateSummary(latestRecords);
        renderTable(latestRecords);
        renderChart(latestRecords);

        if (last) {
            renderLiveData(last);
        }

        renderLock = false;

    }, 300);
}


function safeValue(value) {
    return value === null || value === undefined || value === "" ? "-" : value;
}

function formatDistance(value) {
    if (value === null || value === undefined || value === "" || isNaN(value)) {
        return "-";
    }
    return Number(value).toFixed(2) + " m";
}

function calculateDistanceFromRssi(rssiValue) {
    if (rssiValue === null || rssiValue === undefined || isNaN(rssiValue)) {
        return null;
    }
    return Math.pow(10, (A_REF - Number(rssiValue)) / (10 * N_VAL));
}

function toNumberOrNull(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }
    var numeric = Number(value);
    return isNaN(numeric) ? null : numeric;
}

function normalizeRecord(record) {
    var rssiKf = toNumberOrNull(record.rssi_kf);
    var rssiEma = toNumberOrNull(record.rssi_ema);
    var rssiVar = toNumberOrNull(record.rssi_var);
    var distanceReference = toNumberOrNull(record.distance_reference);
    var distanceML = toNumberOrNull(record.distance_ml);

    if (distanceML == null || isNaN(distanceML)) {
        distanceML = calculateDistanceFromRssi(rssiEma);
    }

    return Object.assign({}, record, {
        rssi_kf: rssiKf !== null ? rssiKf : record.rssi_kf,
        rssi_ema: rssiKf !== null ? rssiKf : (rssiEma !== null ? rssiEma : record.rssi_ema),
        rssi_var: rssiVar !== null ? rssiVar : record.rssi_var,
        distance_reference: distanceReference !== null ? distanceReference : record.distance_reference,
        distance_ml: distanceML
    });
}

function downsampleByTime(records, intervalMs =1000) {
    let result = [];
    let lastTime = 0;
    for (let r of records) {
        let t = new Date(r.timestamp).getTime();

        if (t - lastTime >= intervalMs) {
            result.push(r);
            lastTime = t;
        }
    }
    return result;
}

function renderLiveData(data) {
    var normalized = normalizeRecord(data);
    document.getElementById("data").innerHTML = `
        <p><strong>Gateway:</strong> ${safeValue(normalized.gateway)}</p>
        <p><strong>MAC:</strong> ${safeValue(normalized.mac_address)}</p>
        <p><strong>RSSI:</strong> ${safeValue(normalized.rssi_ema)}</p>
        <p><strong>ML Mesafe:</strong> ${formatDistance(normalized.distance_ml)}</p>
        <p><strong>Durum:</strong> <span class="badge">${safeValue(normalized.durum)}</span></p>
        <p><strong>Zaman:</strong> ${safeValue(normalized.timestamp)}</p>
    `;
}

function updateSummary(records) {
    var lastRecord = records.length ? records[records.length - 1] : null;
    document.getElementById("distanceValue").textContent = lastRecord
        ? formatDistance(lastRecord.distance_ml)
        : "-";
}

function renderTable(records) {
    var tableBody = document.getElementById("tableBody");

    if (!records.length) {
        tableBody.innerHTML = "<tr><td colspan='8'>Kayıt bulunamadı.</td></tr>";
        return;
    }

    tableBody.innerHTML = records.slice().reverse().map(function(record) {
        return `
            <tr>
                <td>${safeValue(record.id)}</td>
                <td>${safeValue(record.timestamp)}</td>
                <td>${safeValue(record.mac_address)}</td>
                <td>${safeValue(record.gateway)}</td>
                <td>${safeValue(record.rssi_ema)}</td>
                <td>${safeValue(record.distance_ml)}</td>
                <td>${safeValue(record.ml_algorithm)}</td>
                <td><span class="badge">${safeValue(record.durum)}</span></td>
            </tr>
        `;
    }).join("");
}

function renderChart(records) {
    var filtered = records.slice(-100);; // 1 saniyede 1 veri olacak şekilde filtrele
    var labels = filtered.map(r => r.timestamp);
    var distanceValues = filtered.map(r => r.distance_ml);  
    

  
 

    if (!historyChart) {
        historyChart = new Chart(document.getElementById("historyChart"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                        label: " Mesafe (m)",
                        data: distanceValues,
                        borderColor: "#16a34a",
                        backgroundColor: "rgba(22, 163, 74, 0.15)",
                        tension: 0.2,
                        elements: {
                            point: {
                                radius: 0
                            }
                        }
                    }]
                
            },
            options: {
               
                animation: false, // 🚀 EN ÖNEMLİ PERFORMANS AYARI
                responsive: true,
                maintainAspectRatio: true,

                interaction: {
                    mode: "index",
                    intersect: false
            },

                plugins: {
                    legend: {
                        display: false
                    }
        },

                elements: {
                     point: {
                        radius: 0 // 🚀 noktaları çizme (çok hız kazandırır)
                    }
         },

                scales: {
                    x: {
                        ticks: {
                            maxTicksLimit: 10 // 🚀 çok label çizmesin
                       }
                   },
                   y: {
                        type: "linear",
                        position: "left",
                        title: {
                             display: true,
                             text: "Mesafe (m)"
            }
        }
    }
}

                  
                    
                
});
        return;
    
    }
    historyChart.data.labels = labels;
    historyChart.data.datasets[0].data = distanceValues;
    historyChart.update("none");
}
function renderChartIncremental(record) {
    if (!historyChart) return;

    historyChart.data.labels.push(record.id ?? record.timestamp);
    historyChart.data.datasets[0].data.push(record.distance_ml);

    // max 100 veri tut
    if (historyChart.data.labels.length > 300) {
        historyChart.data.labels.shift();
        historyChart.data.datasets[0].data.shift();
    }

    historyChart.update("none");

}
function mergeSocketRecord(data) {
    var r = normalizeRecord(data);

    latestRecords.push(r);

    if (latestRecords.length > maxRecordCount) {
        latestRecords.splice(0, latestRecords.length - maxRecordCount);
    }
}

function loadInitialHistory() {
    fetch("/api/veriler")
        .then(r => r.json())
        .then(records => {

            latestRecords = records.map(normalizeRecord);

            updateSummary(latestRecords);
            renderTable(latestRecords);
            renderChart(latestRecords);

            if (latestRecords.length) {
                renderLiveData(latestRecords.at(-1));
            }

        })
        .catch(err => {
            console.error(err);
        });
}

socket.on("connect", function() {
    console.log("Sunucuya bağlandı");
    if (!isInitialResetDone) {
        loadInitialHistory();
        isInitialResetDone = true;
    }
});

socket.on("connect_error", function(err) {
    console.error("Socket baglanti hatasi:", err);
});


socket.on("rssi_update", function(data) {

    var normalized = normalizeRecord(data);
    mergeSocketRecord(normalized);
    renderChartIncremental({
        distance_ml: normalized.distance_ml
    });
    scheduleRender();

});


  