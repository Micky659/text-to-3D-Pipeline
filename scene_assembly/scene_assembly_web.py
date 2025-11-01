import http.server
import socketserver
import json
import os
import urllib.parse
from pathlib import Path

PORT = 8000
OUTPUT_DIR = r"C:\Users\koth_ak\Akshat's Thesis\text-to-3D-Pipeline\output"


class SceneServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # Serve the main HTML page
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html_content().encode())
            return

        # API to list available scene JSON files
        elif parsed_path.path == '/api/list_scenes':
            try:
                scenes = []
                if os.path.exists(OUTPUT_DIR):
                    for item in os.listdir(OUTPUT_DIR):
                        manifest_path = os.path.join(OUTPUT_DIR, item)

                        if os.path.exists(manifest_path):
                            # Get creation time
                            mtime = os.path.getmtime(manifest_path)
                            scenes.append({
                                'name': item,
                                'path': manifest_path,
                                'modified': mtime
                            })

                # Sort by modification time (newest first)
                scenes.sort(key=lambda x: x['modified'], reverse=True)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(scenes).encode())
                return
            except Exception as e:
                print(f"Error listing scenes: {e}")
                self.send_error(500, f'Error listing scenes: {str(e)}')
                return

        # API to load scene with all assets
        elif parsed_path.path == '/api/load_scene':
            query = urllib.parse.parse_qs(parsed_path.query)
            json_path = query.get('path', [None])[0]

            print(f"Loading scene from: {json_path}")

            if not json_path:
                self.send_error(400, 'No path provided')
                return

            if not os.path.exists(json_path):
                print(f"File not found: {json_path}")
                self.send_error(404, f'JSON file not found: {json_path}')
                return

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    scene_data = json.load(f)

                print(f"Loaded scene with {len(scene_data.get('objects', []))} objects")

                # Load all assets
                for obj in scene_data.get('objects', []):
                    obj_path = obj.get('asset', '')
                    if obj_path and os.path.exists(obj_path):
                        print(f"Loading asset: {obj_path}")
                        # Load OBJ file
                        with open(obj_path, 'r', encoding='utf-8') as f:
                            obj['obj_content'] = f.read()

                        # Try to load MTL file
                        mtl_path = obj_path.replace('.obj', '.mtl')
                        if os.path.exists(mtl_path):
                            with open(mtl_path, 'r', encoding='utf-8') as f:
                                obj['mtl_content'] = f.read()

                        # Try to load texture from metadata
                        if 'metadata' in obj and 'texture_image' in obj['metadata']:
                            texture_path = obj['metadata']['texture_image']
                            if os.path.exists(texture_path):
                                import base64
                                with open(texture_path, 'rb') as f:
                                    texture_data = base64.b64encode(f.read()).decode()
                                    ext = os.path.splitext(texture_path)[1].lower()
                                    mime_type = 'image/png' if ext == '.png' else 'image/jpeg'
                                    obj['texture_data'] = f'data:{mime_type};base64,{texture_data}'

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(scene_data).encode())
                return

            except Exception as e:
                print(f"Error loading scene: {e}")
                import traceback
                traceback.print_exc()
                self.send_error(500, f'Error loading scene: {str(e)}')
                return

        # Serve static files
        else:
            super().do_GET()

    def get_html_content(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Scene Visualizer</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .container { display: flex; flex-direction: column; height: 100vh; }
        .header { background: white; padding: 20px 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { margin-bottom: 15px; color: #1f2937; font-size: 28px; }
        .controls { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; align-items: center; }
        select { padding: 10px 15px; border: 2px solid #e5e7eb; border-radius: 8px; flex: 1; min-width: 300px; font-size: 14px; transition: border-color 0.3s; }
        select:focus { outline: none; border-color: #3b82f6; }
        input { padding: 10px 15px; border: 2px solid #e5e7eb; border-radius: 8px; flex: 1; min-width: 300px; font-size: 14px; transition: border-color 0.3s; }
        input:focus { outline: none; border-color: #3b82f6; }
        button { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.3s; }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
        .btn-secondary { background-color: #f3f4f6; color: #374151; }
        .btn-secondary:hover { background-color: #e5e7eb; }
        .btn-active { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
        .message { margin-top: 10px; padding: 12px 16px; border-radius: 8px; font-size: 14px; }
        .error { background-color: #fee; color: #c00; border-left: 4px solid #c00; }
        .success { background-color: #efe; color: #060; border-left: 4px solid #060; }
        .warning { background-color: #fef3c7; color: #92400e; border-left: 4px solid #92400e; }
        .canvas-container { flex: 1; display: flex; align-items: center; justify-content: center; padding: 30px; position: relative; }
        canvas { border-radius: 12px; background-color: white; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
        #canvas2d { border: none; }
        #canvas3d { width: 100%; height: 100%; max-width: 1400px; max-height: 900px; }
        .placeholder { color: white; font-size: 20px; text-align: center; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        .loading { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.95); display: none; align-items: center; justify-content: center; flex-direction: column; z-index: 10; border-radius: 12px; }
        .spinner { border: 6px solid #f3f4f6; border-top: 6px solid #667eea; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .controls-3d { position: absolute; bottom: 30px; left: 30px; background: white; padding: 15px 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-size: 13px; display: none; }
        .footer { background: white; padding: 20px 30px; box-shadow: 0 -4px 6px rgba(0,0,0,0.1); display: none; }
        .info { font-size: 14px; color: #374151; }
        .info p { margin: 8px 0; }
        .info strong { color: #1f2937; }
        .divider { width: 100%; border-top: 2px solid #e5e7eb; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠 3D Scene Visualizer</h1>
            <div class="controls">
                <select id="sceneSelect" onchange="onSceneSelect()">
                    <option value="">-- Select a scene --</option>
                </select>
                <button onclick="loadSelectedScene()" class="btn-primary">Load Scene</button>
                <button onclick="refreshSceneList()" class="btn-secondary">🔄 Refresh</button>
            </div>
            <div class="controls">
                <input type="text" id="jsonPath" placeholder="Or enter custom path (e.g., C:\\path\\to\\manifest.json)">
                <button onclick="loadCustomScene()" class="btn-secondary">Load Custom</button>
            </div>
            <div class="divider"></div>
            <div class="controls">
                <button id="btn2d" onclick="setView('2d')" class="btn-secondary">📐 2D Layout</button>
                <button id="btn3d" onclick="setView('3d')" class="btn-secondary">📦 3D Boxes</button>
                <button id="btnAssets" onclick="setView('assets')" class="btn-secondary">🎨 3D Assets</button>
                <button id="btnSave2D" onclick="save2DLayout()" class="btn-secondary" style="display: none;">💾 Save 2D Layout</button>
            </div>
            <div id="message"></div>
        </div>
        <div class="canvas-container">
            <div id="placeholder" class="placeholder">
                Select a scene from the dropdown or enter a custom path<br>
                and click "Load Scene" to begin
            </div>
            <canvas id="canvas2d" style="display: none;"></canvas>
            <canvas id="canvas3d" style="display: none;"></canvas>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p style="margin-top: 20px; color: #374151; font-weight: 600;">Loading scene and assets...</p>
            </div>
            <div class="controls-3d" id="controls3d">
                <strong>🖱️ Controls:</strong><br>
                <span style="color: #6b7280;">Left Click + Drag: Rotate</span><br>
                <span style="color: #6b7280;">Scroll: Zoom In/Out</span>
            </div>
        </div>
        <div class="footer" id="footer">
            <h3 style="margin-bottom: 10px; color: #1f2937;">📊 Scene Information</h3>
            <div class="info" id="sceneInfo"></div>
        </div>
    </div>

    <script>
        let jsonData = null;
        let currentView = '2d';
        let scene, camera, renderer, animationId;
        let isDragging = false;
        let previousMousePosition = { x: 0, y: 0 };
        let cameraAngle = { theta: Math.PI / 4, phi: Math.PI / 3 };
        let cameraDistance = 8;

        // Load scene list on page load
        window.addEventListener('DOMContentLoaded', refreshSceneList);

        function showMessage(msg, type) {
            const el = document.getElementById('message');
            el.innerHTML = '<div class="message ' + type + '">' + msg + '</div>';
        }

        async function refreshSceneList() {
            try {
                const response = await fetch('/api/list_scenes');
                if (!response.ok) throw new Error('Failed to load scene list');

                const scenes = await response.json();
                const select = document.getElementById('sceneSelect');

                select.innerHTML = '<option value="">-- Select a scene --</option>';

                if (scenes.length === 0) {
                    showMessage('No scenes found in output directory', 'warning');
                    return;
                }

                scenes.forEach(scene => {
                    const option = document.createElement('option');
                    option.value = scene.path;
                    const date = new Date(scene.modified * 1000).toLocaleString();
                    option.textContent = `${scene.name} (${date})`;
                    select.appendChild(option);
                });

                showMessage(`Found ${scenes.length} scene(s)`, 'success');
            } catch (err) {
                console.error('Error loading scene list:', err);
                showMessage('Error loading scene list: ' + err.message, 'error');
            }
        }

        function onSceneSelect() {
            const path = document.getElementById('sceneSelect').value;
            document.getElementById('jsonPath').value = path;
        }

        async function loadSelectedScene() {
            const path = document.getElementById('sceneSelect').value;
            if (!path) {
                showMessage('Please select a scene from the dropdown', 'error');
                return;
            }
            await loadScene(path);
        }

        async function loadCustomScene() {
            const path = document.getElementById('jsonPath').value.trim();
            if (!path) {
                showMessage('Please enter a custom path', 'error');
                return;
            }
            await loadScene(path);
        }

        async function loadScene(path) {
            document.getElementById('loading').style.display = 'flex';
            showMessage('', '');

            try {
                console.log('Loading scene from:', path);
                const response = await fetch('/api/load_scene?path=' + encodeURIComponent(path));

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Failed to load scene: ${response.status} - ${errorText}`);
                }

                jsonData = await response.json();
                console.log('Scene loaded:', jsonData);
                document.getElementById('loading').style.display = 'none';

                const assetsLoaded = jsonData.objects.filter(o => o.obj_content).length;
                showMessage(`✓ Scene loaded! Found ${jsonData.objects.length} objects, ${assetsLoaded} with 3D assets.`, 'success');

                currentView = assetsLoaded > 0 ? 'assets' : '2d';
                updateView();
            } catch (err) {
                console.error('Error loading scene:', err);
                document.getElementById('loading').style.display = 'none';
                showMessage('Error: ' + err.message, 'error');
            }
        }

        function setView(view) {
            if (!jsonData) {
                showMessage('Please load a scene first', 'warning');
                return;
            }
            currentView = view;
            updateView();
        }

        function updateView() {
            document.getElementById('placeholder').style.display = 'none';
            document.getElementById('footer').style.display = 'block';

            document.getElementById('btn2d').className = currentView === '2d' ? 'btn-active' : 'btn-secondary';
            document.getElementById('btn3d').className = currentView === '3d' ? 'btn-active' : 'btn-secondary';
            document.getElementById('btnAssets').className = currentView === 'assets' ? 'btn-active' : 'btn-secondary';

            // Show save button only in 2D view
            document.getElementById('btnSave2D').style.display = currentView === '2d' ? 'inline-block' : 'none';

            updateSceneInfo();

            if (currentView === '2d') {
                document.getElementById('canvas2d').style.display = 'block';
                document.getElementById('canvas3d').style.display = 'none';
                document.getElementById('controls3d').style.display = 'none';
                if (animationId) cancelAnimationFrame(animationId);
                draw2DLayout();
            } else {
                document.getElementById('canvas2d').style.display = 'none';
                document.getElementById('canvas3d').style.display = 'block';
                document.getElementById('controls3d').style.display = 'block';
                init3DScene(currentView === 'assets');
            }
        }

        function updateSceneInfo() {
            const assetsLoaded = jsonData.objects.filter(o => o.obj_content).length;
            document.getElementById('sceneInfo').innerHTML = `
                <p><strong>Scene ID:</strong> ${jsonData.scene_id}</p>
                <p><strong>User Input:</strong> ${jsonData.user_input || 'N/A'}</p>
                <p><strong>Room Dimensions:</strong> ${jsonData.room.w}m × ${jsonData.room.d}m × ${jsonData.room.h}m</p>
                <p><strong>Total Objects:</strong> ${jsonData.objects.length}</p>
                <p><strong>3D Assets Loaded:</strong> ${assetsLoaded}</p>
            `;
        }

        function draw2DLayout() {
            const canvas = document.getElementById('canvas2d');
            const ctx = canvas.getContext('2d');
            const room = jsonData.room;

            const scale = 100;
            const padding = 80;
            const hw = room.w / 2;
            const hd = room.d / 2;

            canvas.width = room.w * scale + padding * 2;
            canvas.height = room.d * scale + padding * 2;

            // Gradient background
            const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
            gradient.addColorStop(0, '#f8fafc');
            gradient.addColorStop(1, '#e2e8f0');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Room bounds with shadow
            ctx.shadowColor = 'rgba(0, 0, 0, 0.1)';
            ctx.shadowBlur = 20;
            ctx.shadowOffsetX = 0;
            ctx.shadowOffsetY = 4;

            ctx.fillStyle = '#ffffff';
            ctx.fillRect(padding, padding, room.w * scale, room.d * scale);

            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = '#1e293b';
            ctx.lineWidth = 3;
            ctx.strokeRect(padding, padding, room.w * scale, room.d * scale);

            // Grid
            ctx.strokeStyle = '#e2e8f0';
            ctx.lineWidth = 1;
            for (let i = 0; i <= room.w; i++) {
                ctx.beginPath();
                ctx.moveTo(padding + i * scale, padding);
                ctx.lineTo(padding + i * scale, padding + room.d * scale);
                ctx.stroke();
            }
            for (let i = 0; i <= room.d; i++) {
                ctx.beginPath();
                ctx.moveTo(padding, padding + i * scale);
                ctx.lineTo(padding + room.w * scale, padding + i * scale);
                ctx.stroke();
            }

            // Origin marker
            const originX = padding + hw * scale;
            const originZ = padding + hd * scale;

            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(originX, originZ, 8, 0, 2 * Math.PI);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(originX - 12, originZ);
            ctx.lineTo(originX + 12, originZ);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(originX, originZ - 12);
            ctx.lineTo(originX, originZ + 12);
            ctx.stroke();

            ctx.fillStyle = '#ef4444';
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('Origin (0, 0)', originX + 15, originZ + 5);

            // Draw objects
            const categoryColors = {
                bed: { fill: '#dc2626', stroke: '#991b1b' },
                chair: { fill: '#d97706', stroke: '#92400e' },
                sofa: { fill: '#2563eb', stroke: '#1e40af' },
                table: { fill: '#7c2d12', stroke: '#431407' },
                desk: { fill: '#7c2d12', stroke: '#431407' },
                lamp: { fill: '#eab308', stroke: '#a16207' },
                nightstand: { fill: '#92400e', stroke: '#78350f' },
                cabinet: { fill: '#78350f', stroke: '#451a03' },
                default: { fill: '#64748b', stroke: '#334155' }
            };

            jsonData.objects.forEach((obj, idx) => {
                const x = padding + (obj.position[0] + hw) * scale;
                const z = padding + (obj.position[2] + hd) * scale;
                const width = obj.bbox[0] * scale;
                const depth = obj.bbox[1] * scale;

                const colors = categoryColors[obj.category] || categoryColors.default;

                ctx.save();
                ctx.translate(x, z);
                ctx.rotate((obj.rotation_yaw * Math.PI) / 180);

                // Shadow
                ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
                ctx.shadowBlur = 10;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 3;

                // Object fill
                ctx.fillStyle = colors.fill;
                ctx.fillRect(-width / 2, -depth / 2, width, depth);

                ctx.shadowColor = 'transparent';

                // Object stroke
                ctx.strokeStyle = colors.stroke;
                ctx.lineWidth = 2;
                ctx.strokeRect(-width / 2, -depth / 2, width, depth);

                ctx.restore();

                // Label with background
                ctx.shadowColor = 'rgba(0, 0, 0, 0.1)';
                ctx.shadowBlur = 5;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 2;

                ctx.fillStyle = 'white';
                ctx.font = 'bold 11px sans-serif';
                const textWidth = ctx.measureText(obj.id).width;
                ctx.fillRect(x - textWidth / 2 - 5, z + 8, textWidth + 10, 18);

                ctx.shadowColor = 'transparent';

                ctx.strokeStyle = colors.stroke;
                ctx.lineWidth = 1;
                ctx.strokeRect(x - textWidth / 2 - 5, z + 8, textWidth + 10, 18);

                ctx.fillStyle = '#1e293b';
                ctx.textAlign = 'center';
                ctx.fillText(obj.id, x, z + 21);
            });

            // Legend
            ctx.font = 'bold 16px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillStyle = '#1e293b';
            ctx.fillText(`Room: ${room.w}m × ${room.d}m × ${room.h}m`, 15, 30);
        }

        function parseOBJ(text) {
            const vertices = [];
            const normals = [];
            const uvs = [];
            const faces = [];

            const lines = text.split('\\n');
            for (let line of lines) {
                line = line.trim();
                if (!line || line.startsWith('#')) continue;

                const parts = line.split(/\\s+/);
                const type = parts[0];

                if (type === 'v') {
                    vertices.push(parseFloat(parts[1]), parseFloat(parts[2]), parseFloat(parts[3]));
                } else if (type === 'vn') {
                    normals.push(parseFloat(parts[1]), parseFloat(parts[2]), parseFloat(parts[3]));
                } else if (type === 'vt') {
                    uvs.push(parseFloat(parts[1]), parseFloat(parts[2]));
                } else if (type === 'f') {
                    for (let i = 1; i < parts.length; i++) {
                        const indices = parts[i].split('/');
                        faces.push({
                            v: parseInt(indices[0]) - 1,
                            vt: indices[1] ? parseInt(indices[1]) - 1 : -1,
                            vn: indices[2] ? parseInt(indices[2]) - 1 : -1
                        });
                    }
                }
            }
            return { vertices, normals, uvs, faces };
        }

        function createGeometryFromOBJ(objData) {
            const geometry = new THREE.BufferGeometry();
            const positions = [];
            const normalsArray = [];
            const uvsArray = [];

            for (let i = 0; i < objData.faces.length; i += 3) {
                for (let j = 0; j < 3; j++) {
                    const face = objData.faces[i + j];
                    positions.push(
                        objData.vertices[face.v * 3],
                        objData.vertices[face.v * 3 + 1],
                        objData.vertices[face.v * 3 + 2]
                    );
                    if (face.vn >= 0 && objData.normals.length > 0) {
                        normalsArray.push(
                            objData.normals[face.vn * 3],
                            objData.normals[face.vn * 3 + 1],
                            objData.normals[face.vn * 3 + 2]
                        );
                    }
                    if (face.vt >= 0 && objData.uvs.length > 0) {
                        uvsArray.push(objData.uvs[face.vt * 2], objData.uvs[face.vt * 2 + 1]);
                    }
                }
            }

            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            if (normalsArray.length > 0) {
                geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normalsArray, 3));
            } else {
                geometry.computeVertexNormals();
            }
            if (uvsArray.length > 0) {
                geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvsArray, 2));
            }
            return geometry;
        }

        function init3DScene(useAssets) {
            const canvas = document.getElementById('canvas3d');
            const room = jsonData.room;

            if (scene) {
                while(scene.children.length > 0) scene.remove(scene.children[0]);
            }

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);

            camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
            cameraDistance = Math.max(room.w, room.d, room.h) * 1.5;
            updateCameraPosition();

            if (renderer) renderer.dispose();
            renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
            renderer.setSize(canvas.clientWidth, canvas.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);

            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);

            const light1 = new THREE.DirectionalLight(0xffffff, 0.8);
            light1.position.set(room.w, room.h * 2, room.d);
            scene.add(light1);

            const light2 = new THREE.DirectionalLight(0xffffff, 0.4);
            light2.position.set(-room.w, room.h, -room.d);
            scene.add(light2);

            // Room
            const roomGeo = new THREE.BoxGeometry(room.w, room.h, room.d);
            const roomMat = new THREE.MeshBasicMaterial({ 
                color: 0xffffff, 
                side: THREE.BackSide, 
                transparent: true, 
                opacity: 0.1 
            });
            const roomMesh = new THREE.Mesh(roomGeo, roomMat);
            roomMesh.position.set(0, room.h / 2, 0);
            scene.add(roomMesh);

            const edges = new THREE.EdgesGeometry(roomGeo);
            const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x000000 }));
            line.position.set(0, room.h / 2, 0);
            scene.add(line);

            const gridHelper = new THREE.GridHelper(Math.max(room.w, room.d), 10);
            gridHelper.position.set(0, 0, 0);
            scene.add(gridHelper);

            // Objects
            jsonData.objects.forEach((obj) => {
                let mesh;

                if (useAssets && obj.obj_content) {
                    const objData = parseOBJ(obj.obj_content);
                    const geometry = createGeometryFromOBJ(objData);

                    let material;
                    if (obj.texture_data) {
                        const texture = new THREE.TextureLoader().load(obj.texture_data);
                        material = new THREE.MeshPhongMaterial({ map: texture });
                    } else {
                        material = new THREE.MeshPhongMaterial({ color: 0xcccccc });
                    }

                    mesh = new THREE.Mesh(geometry, material);

                } else {
                    const geometry = new THREE.BoxGeometry(obj.bbox[0], obj.bbox[2], obj.bbox[1]);
                    const colors = { 
                        table: 0x8B4513, chair: 0xDAA520, sofa: 0x4169E1, 
                        bed: 0xDC143C, lamp: 0xFFD700, desk: 0x8B4513,
                        nightstand: 0xA0522D, cabinet: 0x654321,
                        default: 0x696969 
                    };
                    const material = new THREE.MeshPhongMaterial({ 
                        color: colors[obj.category] || colors.default 
                    });
                    mesh = new THREE.Mesh(geometry, material);

                    const edgesGeo = new THREE.EdgesGeometry(geometry);
                    const edgesMesh = new THREE.LineSegments(
                        edgesGeo, 
                        new THREE.LineBasicMaterial({ color: 0x000000 })
                    );
                    mesh.add(edgesMesh);
                }

                mesh.position.set(obj.position[0], obj.position[1], obj.position[2]);
                mesh.rotation.y = (obj.rotation_yaw * Math.PI) / 180;

                scene.add(mesh);

                // Label
                const canvas2d = document.createElement('canvas');
                const context = canvas2d.getContext('2d');
                canvas2d.width = 256;
                canvas2d.height = 64;
                context.fillStyle = '#ffffff';
                context.fillRect(0, 0, 256, 64);
                context.fillStyle = '#000000';
                context.font = 'Bold 24px Arial';
                context.textAlign = 'center';
                context.fillText(obj.id, 128, 40);

                const texture = new THREE.CanvasTexture(canvas2d);
                const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture }));
                sprite.position.set(0, obj.bbox[2] / 2 + 0.3, 0);
                sprite.scale.set(0.5, 0.125, 1);
                mesh.add(sprite);
            });

            setupControls(canvas);
            animate();
        }
        
        function save2DLayout() {
            const canvas = document.getElementById('canvas2d');
            if (!canvas) {
                showMessage('2D canvas not found', 'error');
                return;
            }
        
            // Convert canvas to PNG
            const link = document.createElement('a');
            link.download = (jsonData?.scene_id || 'scene') + '_layout.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        
            showMessage('2D layout saved as PNG!', 'success');
        }

        function updateCameraPosition() {
            const room = jsonData.room;
            camera.position.x = cameraDistance * Math.sin(cameraAngle.theta) * Math.cos(cameraAngle.phi);
            camera.position.y = cameraDistance * Math.sin(cameraAngle.phi);
            camera.position.z = cameraDistance * Math.cos(cameraAngle.theta) * Math.cos(cameraAngle.phi);
            camera.lookAt(0, room.h / 4, 0);
        }

        function setupControls(canvas) {
            canvas.addEventListener('mousedown', (e) => {
                isDragging = true;
                previousMousePosition.x = e.clientX;
                previousMousePosition.y = e.clientY;
                canvas.style.cursor = 'grabbing';
            });

            canvas.addEventListener('mouseup', () => { 
                isDragging = false; 
                canvas.style.cursor = 'grab';
            });

            canvas.addEventListener('mouseleave', () => { 
                isDragging = false; 
                canvas.style.cursor = 'grab';
            });

            canvas.addEventListener('mousemove', (e) => {
                if (!isDragging) return;

                const deltaX = e.clientX - previousMousePosition.x;
                const deltaY = e.clientY - previousMousePosition.y;

                cameraAngle.theta -= deltaX * 0.01;
                cameraAngle.phi += deltaY * 0.01;
                cameraAngle.phi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraAngle.phi));

                previousMousePosition.x = e.clientX;
                previousMousePosition.y = e.clientY;

                updateCameraPosition();
            });

            canvas.addEventListener('wheel', (e) => {
                e.preventDefault();
                cameraDistance += e.deltaY * 0.01;
                cameraDistance = Math.max(2, Math.min(50, cameraDistance));
                updateCameraPosition();
            }, { passive: false });

            canvas.style.cursor = 'grab';
        }

        function animate() {
            animationId = requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
    </script>
</body>
</html>'''


def run_server():
    with socketserver.TCPServer(("", PORT), SceneServerHandler) as httpd:
        print(f"\n{'=' * 60}")
        print(f"  3D Scene Visualizer Server Running")
        print(f"{'=' * 60}")
        print(f"\n  Output Directory: {OUTPUT_DIR}")
        print(f"\n  Open your browser and go to:")
        print(f"  http://localhost:{PORT}")
        print(f"\n  To stop the server, press Ctrl+C")
        print(f"\n{'=' * 60}\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    run_server()