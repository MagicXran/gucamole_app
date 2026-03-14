/**
 * VTK.js 3D 仿真查看器 - 核心逻辑
 *
 * 数据驱动渲染 PoC：通过 WebGL 在浏览器端渲染仿真结果，
 * 对比 Guacamole 像素推流的带宽/CPU/延迟差异。
 */

// ---- VTK.js 模块导入 (通过 importmap → esm.sh CDN) ----
import '@kitware/vtk.js/Rendering/Profiles/Geometry';

import vtkGenericRenderWindow  from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow';
import vtkActor                from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkMapper               from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkXMLPolyDataReader    from '@kitware/vtk.js/IO/XML/XMLPolyDataReader';
import vtkXMLUnstructuredGridReader from '@kitware/vtk.js/IO/XML/XMLUnstructuredGridReader';
import vtkSTLReader            from '@kitware/vtk.js/IO/Geometry/STLReader';
import vtkOBJReader            from '@kitware/vtk.js/IO/Misc/OBJReader';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import vtkColorMaps            from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps';
import vtkScalarBarActor       from '@kitware/vtk.js/Rendering/Core/ScalarBarActor';
import vtkAxesActor            from '@kitware/vtk.js/Rendering/Core/AxesActor';
import vtkInteractorStyleTrackballCamera from '@kitware/vtk.js/Interaction/Style/InteractorStyleTrackballCamera';

// ---- 认证工具 ----
function getToken() { return localStorage.getItem('portal_token'); }
function authHeaders() { return { 'Authorization': 'Bearer ' + getToken() }; }

// ---- 状态 ----
let renderWindow = null;
let renderer = null;
let grw = null;
let currentActor = null;
let scalarBarActor = null;
let axesActor = null;
let currentPolyData = null;
let fpsFrames = 0;
let fpsLastTime = performance.now();

// ---- DOM 元素 ----
const $renderArea     = document.getElementById('render-area');
const $welcomeOverlay = document.getElementById('welcome-overlay');
const $loadingOverlay = document.getElementById('loading-overlay');
const $loadingText    = document.getElementById('loading-text');
const $errorToast     = document.getElementById('error-toast');
const $statusBar      = document.getElementById('status-bar');
const $fpsValue       = document.getElementById('fps-value');
const $vertexCount    = document.getElementById('vertex-count');
const $cellCount      = document.getElementById('cell-count');
const $fileSize       = document.getElementById('file-size');
const $modelInfo      = document.getElementById('model-info');
const $datasetList    = document.getElementById('dataset-list');
const $datasetLoading = document.getElementById('dataset-loading');
const $datasetEmpty   = document.getElementById('dataset-empty');
const $colorPreset    = document.getElementById('color-preset');
const $scalarSelect   = document.getElementById('scalar-select');
const $representation = document.getElementById('representation');
const $opacityRange   = document.getElementById('opacity-range');
const $toggleAxes     = document.getElementById('toggle-axes');
const $btnResetCamera = document.getElementById('btn-reset-camera');


// ============================================================
// 初始化 VTK.js 渲染器
// ============================================================
function initVTK() {
    grw = vtkGenericRenderWindow.newInstance();
    grw.setContainer($renderArea);

    // 尺寸跟随容器
    const { width, height } = $renderArea.getBoundingClientRect();
    grw.resize();

    renderer = grw.getRenderer();
    renderWindow = grw.getRenderWindow();

    // 交互模式: Trackball Camera
    const interactor = grw.getInteractor();
    interactor.setInteractorStyle(
        vtkInteractorStyleTrackballCamera.newInstance()
    );

    // 背景色
    renderer.setBackground(0.05, 0.07, 0.09);

    // 窗口缩放
    window.addEventListener('resize', function() {
        grw.resize();
        renderWindow.render();
    });

    // FPS 计数器
    startFPSCounter();
}


// ============================================================
// 加载数据集列表
// ============================================================
async function loadDatasetList() {
    try {
        var resp = await fetch('/api/datasets/', { headers: authHeaders() });
        if (resp.status === 401) {
            window.location.href = '/login.html';
            return;
        }
        if (!resp.ok) throw new Error('HTTP ' + resp.status);

        var datasets = await resp.json();
        $datasetLoading.style.display = 'none';

        if (datasets.length === 0) {
            $datasetEmpty.style.display = 'block';
            return;
        }

        $datasetList.style.display = 'block';
        $datasetList.innerHTML = '';

        datasets.forEach(function(ds) {
            var li = document.createElement('li');
            li.className = 'dataset-item';
            li.onclick = function() { loadDataset(ds.filename, ds.size_human, li); };

            var nameSpan = document.createElement('span');
            nameSpan.className = 'dataset-item__name';
            nameSpan.textContent = ds.filename;

            var sizeSpan = document.createElement('span');
            sizeSpan.className = 'dataset-item__size';
            sizeSpan.textContent = ds.size_human;

            li.appendChild(nameSpan);
            li.appendChild(sizeSpan);
            $datasetList.appendChild(li);
        });
    } catch (e) {
        $datasetLoading.textContent = '加载失败: ' + e.message;
    }
}


// ============================================================
// 加载并渲染数据集
// ============================================================
async function loadDataset(filename, sizeHuman, listItem) {
    // 高亮选中项
    document.querySelectorAll('.dataset-item--active').forEach(function(el) {
        el.classList.remove('dataset-item--active');
    });
    if (listItem) listItem.classList.add('dataset-item--active');

    // 显示加载状态
    $welcomeOverlay.classList.add('render-overlay--hidden');
    $loadingOverlay.classList.remove('render-overlay--hidden');
    $loadingText.textContent = '正在下载 ' + filename + '...';
    hideError();

    try {
        // 1. 下载文件
        var startTime = performance.now();
        var resp = await fetch('/api/datasets/' + encodeURIComponent(filename), {
            headers: authHeaders(),
        });
        if (!resp.ok) throw new Error('下载失败: HTTP ' + resp.status);

        var arrayBuffer = await resp.arrayBuffer();
        var downloadTime = ((performance.now() - startTime) / 1000).toFixed(2);

        $loadingText.textContent = '解析 ' + filename + '...';

        // 2. 根据扩展名选择 Reader
        var ext = filename.split('.').pop().toLowerCase();
        var reader = createReader(ext);
        if (!reader) {
            throw new Error('不支持的格式: .' + ext);
        }

        // 3. 解析数据
        parseData(reader, arrayBuffer, ext);

        // 4. 获取输出
        var output = reader.getOutputData(0);
        if (!output) throw new Error('解析失败：无输出数据');

        currentPolyData = output;

        // 5. 清除旧 actor
        if (currentActor) {
            renderer.removeActor(currentActor);
            currentActor = null;
        }
        if (scalarBarActor) {
            renderer.removeActor(scalarBarActor);
            scalarBarActor = null;
        }

        // 6. 创建 mapper + actor
        var mapper = vtkMapper.newInstance();
        mapper.setInputData(output);

        currentActor = vtkActor.newInstance();
        currentActor.setMapper(mapper);
        renderer.addActor(currentActor);

        // 7. 提取标量场列表
        populateScalarFields(output);

        // 8. 应用当前显示设置
        applyRepresentation();
        applyOpacity();

        // 9. 重置相机
        renderer.resetCamera();
        renderWindow.render();

        // 10. 更新状态栏
        var nPoints = output.getNumberOfPoints ? output.getNumberOfPoints() : 0;
        var nCells  = output.getNumberOfCells  ? output.getNumberOfCells()  : 0;
        $vertexCount.textContent = nPoints.toLocaleString();
        $cellCount.textContent   = nCells.toLocaleString();
        $fileSize.textContent    = sizeHuman;
        $statusBar.style.display = 'flex';

        $modelInfo.innerHTML =
            '<strong>' + escapeHtml(filename) + '</strong><br>' +
            '顶点: ' + nPoints.toLocaleString() + '<br>' +
            '单元: ' + nCells.toLocaleString() + '<br>' +
            '下载: ' + downloadTime + 's<br>' +
            '大小: ' + sizeHuman;

        // 隐藏加载提示
        $loadingOverlay.classList.add('render-overlay--hidden');

    } catch (e) {
        $loadingOverlay.classList.add('render-overlay--hidden');
        $welcomeOverlay.classList.remove('render-overlay--hidden');
        showError(e.message);
        console.error('加载数据集失败:', e);
    }
}


// ============================================================
// Reader 工厂
// ============================================================
function createReader(ext) {
    switch (ext) {
        case 'vtp': return vtkXMLPolyDataReader.newInstance();
        case 'vtu': return vtkXMLUnstructuredGridReader.newInstance();
        case 'stl': return vtkSTLReader.newInstance();
        case 'obj': return vtkOBJReader.newInstance();
        default:    return null;
    }
}

function parseData(reader, arrayBuffer, ext) {
    if (ext === 'vtp' || ext === 'vtu') {
        reader.parseAsArrayBuffer(arrayBuffer);
    } else if (ext === 'stl') {
        reader.parseAsArrayBuffer(arrayBuffer);
    } else if (ext === 'obj') {
        var text = new TextDecoder().decode(arrayBuffer);
        reader.parseAsText(text);
    }
}


// ============================================================
// 标量场
// ============================================================
function populateScalarFields(polyData) {
    $scalarSelect.innerHTML = '<option value="">无 (纯几何)</option>';

    // PointData
    var pd = polyData.getPointData ? polyData.getPointData() : null;
    if (pd) {
        for (var i = 0; i < pd.getNumberOfArrays(); i++) {
            var arr = pd.getArrayByIndex(i);
            if (arr && arr.getNumberOfComponents() === 1) {
                var opt = document.createElement('option');
                opt.value = 'point:' + arr.getName();
                opt.textContent = arr.getName() + ' (点)';
                $scalarSelect.appendChild(opt);
            }
        }
    }

    // CellData
    var cd = polyData.getCellData ? polyData.getCellData() : null;
    if (cd) {
        for (var i = 0; i < cd.getNumberOfArrays(); i++) {
            var arr = cd.getArrayByIndex(i);
            if (arr && arr.getNumberOfComponents() === 1) {
                var opt = document.createElement('option');
                opt.value = 'cell:' + arr.getName();
                opt.textContent = arr.getName() + ' (单元)';
                $scalarSelect.appendChild(opt);
            }
        }
    }
}

function applyScalarField() {
    if (!currentActor || !currentPolyData) return;

    var mapper = currentActor.getMapper();
    var val = $scalarSelect.value;

    // 移除旧标量条
    if (scalarBarActor) {
        renderer.removeActor(scalarBarActor);
        scalarBarActor = null;
    }

    if (!val) {
        // 无标量场：纯几何颜色
        mapper.setScalarVisibility(false);
        currentActor.getProperty().setColor(0.8, 0.8, 0.9);
        renderWindow.render();
        return;
    }

    var parts = val.split(':');
    var location = parts[0]; // 'point' or 'cell'
    var arrayName = parts[1];

    // 获取数据数组
    var dataArray;
    if (location === 'point') {
        mapper.setScalarModeToUsePointFieldData();
        dataArray = currentPolyData.getPointData().getArrayByName(arrayName);
    } else {
        mapper.setScalarModeToUseCellFieldData();
        dataArray = currentPolyData.getCellData().getArrayByName(arrayName);
    }

    if (!dataArray) return;

    mapper.setColorByArrayName(arrayName);
    mapper.setScalarVisibility(true);

    // 颜色映射
    var range = dataArray.getRange();
    var lut = vtkColorTransferFunction.newInstance();
    var preset = vtkColorMaps.getPresetByName($colorPreset.value);
    if (preset) {
        lut.applyColorMap(preset);
    }
    lut.setMappingRange(range[0], range[1]);
    lut.updateRange();
    mapper.setLookupTable(lut);

    // 标量条
    scalarBarActor = vtkScalarBarActor.newInstance();
    scalarBarActor.setScalarsToColors(lut);
    renderer.addActor(scalarBarActor);

    renderWindow.render();
}


// ============================================================
// 显示设置
// ============================================================
function applyRepresentation() {
    if (!currentActor) return;
    var val = parseInt($representation.value, 10);
    var prop = currentActor.getProperty();

    if (val === 3) {
        // Surface + Edges
        prop.setRepresentation(2); // Surface
        prop.setEdgeVisibility(true);
        prop.setEdgeColor(0.2, 0.2, 0.3);
    } else {
        prop.setRepresentation(val);
        prop.setEdgeVisibility(false);
    }
    renderWindow.render();
}

function applyOpacity() {
    if (!currentActor) return;
    currentActor.getProperty().setOpacity(parseFloat($opacityRange.value));
    renderWindow.render();
}


// ============================================================
// 坐标轴
// ============================================================
function toggleAxes() {
    if ($toggleAxes.checked) {
        if (!axesActor) {
            axesActor = vtkAxesActor.newInstance();
        }
        renderer.addActor(axesActor);
    } else if (axesActor) {
        renderer.removeActor(axesActor);
    }
    renderWindow.render();
}


// ============================================================
// FPS 计数器
// ============================================================
function startFPSCounter() {
    function countFrame() {
        fpsFrames++;
        var now = performance.now();
        if (now - fpsLastTime >= 1000) {
            $fpsValue.textContent = fpsFrames;
            fpsFrames = 0;
            fpsLastTime = now;
        }
        requestAnimationFrame(countFrame);
    }
    requestAnimationFrame(countFrame);
}


// ============================================================
// 工具函数
// ============================================================
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function showError(msg) {
    $errorToast.textContent = msg;
    $errorToast.classList.remove('error-toast--hidden');
    setTimeout(function() {
        $errorToast.classList.add('error-toast--hidden');
    }, 5000);
}

function hideError() {
    $errorToast.classList.add('error-toast--hidden');
}


// ============================================================
// 事件绑定
// ============================================================
$colorPreset.addEventListener('change', applyScalarField);
$scalarSelect.addEventListener('change', applyScalarField);
$representation.addEventListener('change', applyRepresentation);
$opacityRange.addEventListener('input', applyOpacity);
$toggleAxes.addEventListener('change', toggleAxes);
$btnResetCamera.addEventListener('click', function() {
    if (renderer) {
        renderer.resetCamera();
        renderWindow.render();
    }
});


// ============================================================
// 启动
// ============================================================
(function main() {
    if (!getToken()) {
        window.location.href = '/login.html';
        return;
    }
    initVTK();
    toggleAxes(); // 默认显示坐标轴
    loadDatasetList();
})();
