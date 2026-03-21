"""
生成示例 VTP 数据文件 — 不依赖 VTK Python 库

VTP (VTK XML PolyData) 是纯 XML 格式，可以手写。
生成一个带标量场的球体网格和一个简单立方体，供 PoC 测试。

使用方法: python data/generate_samples.py
"""

import math
import os
import struct
import base64
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(SCRIPT_DIR, "samples")


def generate_sphere_vtp(filename, n_phi=32, n_theta=16, radius=1.0):
    """生成球体 VTP 文件（含标量场：高度 + 径向距离）"""
    points = []
    height_scalars = []
    radial_scalars = []

    # 生成顶点（球坐标 → 笛卡尔坐标）
    for i in range(n_theta + 1):
        theta = math.pi * i / n_theta
        for j in range(n_phi):
            phi = 2.0 * math.pi * j / n_phi
            x = radius * math.sin(theta) * math.cos(phi)
            y = radius * math.sin(theta) * math.sin(phi)
            z = radius * math.cos(theta)
            points.append((x, y, z))
            height_scalars.append(z)
            # 到 XY 平面的距离
            radial_scalars.append(math.sqrt(x * x + y * y))

    # 生成三角面片
    polys = []
    for i in range(n_theta):
        for j in range(n_phi):
            p0 = i * n_phi + j
            p1 = i * n_phi + (j + 1) % n_phi
            p2 = (i + 1) * n_phi + (j + 1) % n_phi
            p3 = (i + 1) * n_phi + j
            # 两个三角形组成一个四边形
            polys.append((p0, p1, p2))
            polys.append((p0, p2, p3))

    # 写 VTP XML
    n_points = len(points)
    n_polys = len(polys)

    lines = []
    lines.append('<?xml version="1.0"?>')
    lines.append('<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">')
    lines.append('  <PolyData>')
    lines.append('    <Piece NumberOfPoints="{}" NumberOfPolys="{}">'.format(n_points, n_polys))

    # PointData (标量场)
    lines.append('      <PointData Scalars="Height">')
    lines.append('        <DataArray type="Float32" Name="Height" format="ascii">')
    lines.append('          ' + ' '.join('{:.6f}'.format(s) for s in height_scalars))
    lines.append('        </DataArray>')
    lines.append('        <DataArray type="Float32" Name="RadialDist" format="ascii">')
    lines.append('          ' + ' '.join('{:.6f}'.format(s) for s in radial_scalars))
    lines.append('        </DataArray>')
    lines.append('      </PointData>')

    # Points
    lines.append('      <Points>')
    lines.append('        <DataArray type="Float32" NumberOfComponents="3" format="ascii">')
    coords = []
    for p in points:
        coords.extend(['{:.6f}'.format(c) for c in p])
    lines.append('          ' + ' '.join(coords))
    lines.append('        </DataArray>')
    lines.append('      </Points>')

    # Polys
    lines.append('      <Polys>')
    # connectivity
    lines.append('        <DataArray type="Int32" Name="connectivity" format="ascii">')
    conn = []
    for tri in polys:
        conn.extend([str(v) for v in tri])
    lines.append('          ' + ' '.join(conn))
    lines.append('        </DataArray>')
    # offsets
    lines.append('        <DataArray type="Int32" Name="offsets" format="ascii">')
    offsets = [str(3 * (i + 1)) for i in range(n_polys)]
    lines.append('          ' + ' '.join(offsets))
    lines.append('        </DataArray>')
    lines.append('      </Polys>')

    lines.append('    </Piece>')
    lines.append('  </PolyData>')
    lines.append('</VTKFile>')

    filepath = os.path.join(SAMPLES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('  Generated: {} ({} points, {} triangles)'.format(filename, n_points, n_polys))


def generate_cube_vtp(filename):
    """生成立方体 VTP 文件（含标量场：顶点高度）"""
    # 8 个顶点
    points = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5),
        (0.5,  0.5, -0.5), (-0.5,  0.5, -0.5),
        (-0.5, -0.5,  0.5), (0.5, -0.5,  0.5),
        (0.5,  0.5,  0.5), (-0.5,  0.5,  0.5),
    ]
    # 12 个三角形（6 个面，每面 2 个三角形）
    polys = [
        (0, 1, 2), (0, 2, 3),  # bottom
        (4, 6, 5), (4, 7, 6),  # top
        (0, 4, 5), (0, 5, 1),  # front
        (2, 6, 7), (2, 7, 3),  # back
        (0, 3, 7), (0, 7, 4),  # left
        (1, 5, 6), (1, 6, 2),  # right
    ]
    scalars = [p[2] for p in points]  # Z 坐标作为标量

    n_points = len(points)
    n_polys = len(polys)

    lines = []
    lines.append('<?xml version="1.0"?>')
    lines.append('<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">')
    lines.append('  <PolyData>')
    lines.append('    <Piece NumberOfPoints="{}" NumberOfPolys="{}">'.format(n_points, n_polys))

    lines.append('      <PointData Scalars="Height">')
    lines.append('        <DataArray type="Float32" Name="Height" format="ascii">')
    lines.append('          ' + ' '.join('{:.6f}'.format(s) for s in scalars))
    lines.append('        </DataArray>')
    lines.append('      </PointData>')

    lines.append('      <Points>')
    lines.append('        <DataArray type="Float32" NumberOfComponents="3" format="ascii">')
    coords = []
    for p in points:
        coords.extend(['{:.6f}'.format(c) for c in p])
    lines.append('          ' + ' '.join(coords))
    lines.append('        </DataArray>')
    lines.append('      </Points>')

    lines.append('      <Polys>')
    lines.append('        <DataArray type="Int32" Name="connectivity" format="ascii">')
    conn = []
    for tri in polys:
        conn.extend([str(v) for v in tri])
    lines.append('          ' + ' '.join(conn))
    lines.append('        </DataArray>')
    lines.append('        <DataArray type="Int32" Name="offsets" format="ascii">')
    offsets = [str(3 * (i + 1)) for i in range(n_polys)]
    lines.append('          ' + ' '.join(offsets))
    lines.append('        </DataArray>')
    lines.append('      </Polys>')

    lines.append('    </Piece>')
    lines.append('  </PolyData>')
    lines.append('</VTKFile>')

    filepath = os.path.join(SAMPLES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('  Generated: {} ({} points, {} triangles)'.format(filename, n_points, n_polys))


def generate_torus_vtp(filename, R=1.0, r=0.3, n_u=48, n_v=24):
    """生成圆环 (Torus) VTP 文件（含多个标量场，模拟仿真结果）"""
    points = []
    height_scalars = []
    pressure_scalars = []
    temperature_scalars = []

    for i in range(n_u):
        u = 2.0 * math.pi * i / n_u
        for j in range(n_v):
            v = 2.0 * math.pi * j / n_v
            x = (R + r * math.cos(v)) * math.cos(u)
            y = (R + r * math.cos(v)) * math.sin(u)
            z = r * math.sin(v)
            points.append((x, y, z))
            height_scalars.append(z)
            # 模拟"压力"标量场
            pressure_scalars.append(math.sin(u * 3) * math.cos(v * 2) * 100 + 500)
            # 模拟"温度"标量场
            temperature_scalars.append(20 + 80 * (0.5 + 0.5 * math.sin(u + v)))

    polys = []
    for i in range(n_u):
        for j in range(n_v):
            p0 = i * n_v + j
            p1 = i * n_v + (j + 1) % n_v
            p2 = ((i + 1) % n_u) * n_v + (j + 1) % n_v
            p3 = ((i + 1) % n_u) * n_v + j
            polys.append((p0, p1, p2))
            polys.append((p0, p2, p3))

    n_points = len(points)
    n_polys = len(polys)

    lines = []
    lines.append('<?xml version="1.0"?>')
    lines.append('<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">')
    lines.append('  <PolyData>')
    lines.append('    <Piece NumberOfPoints="{}" NumberOfPolys="{}">'.format(n_points, n_polys))

    lines.append('      <PointData Scalars="Pressure">')
    lines.append('        <DataArray type="Float32" Name="Height" format="ascii">')
    lines.append('          ' + ' '.join('{:.4f}'.format(s) for s in height_scalars))
    lines.append('        </DataArray>')
    lines.append('        <DataArray type="Float32" Name="Pressure" format="ascii">')
    lines.append('          ' + ' '.join('{:.4f}'.format(s) for s in pressure_scalars))
    lines.append('        </DataArray>')
    lines.append('        <DataArray type="Float32" Name="Temperature" format="ascii">')
    lines.append('          ' + ' '.join('{:.4f}'.format(s) for s in temperature_scalars))
    lines.append('        </DataArray>')
    lines.append('      </PointData>')

    lines.append('      <Points>')
    lines.append('        <DataArray type="Float32" NumberOfComponents="3" format="ascii">')
    coords = []
    for p in points:
        coords.extend(['{:.6f}'.format(c) for c in p])
    lines.append('          ' + ' '.join(coords))
    lines.append('        </DataArray>')
    lines.append('      </Points>')

    lines.append('      <Polys>')
    lines.append('        <DataArray type="Int32" Name="connectivity" format="ascii">')
    conn = []
    for tri in polys:
        conn.extend([str(v) for v in tri])
    lines.append('          ' + ' '.join(conn))
    lines.append('        </DataArray>')
    lines.append('        <DataArray type="Int32" Name="offsets" format="ascii">')
    offsets = [str(3 * (i + 1)) for i in range(n_polys)]
    lines.append('          ' + ' '.join(offsets))
    lines.append('        </DataArray>')
    lines.append('      </Polys>')

    lines.append('    </Piece>')
    lines.append('  </PolyData>')
    lines.append('</VTKFile>')

    filepath = os.path.join(SAMPLES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('  Generated: {} ({} points, {} triangles)'.format(filename, n_points, n_polys))


def main():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    print('Generating sample VTP files in {}'.format(SAMPLES_DIR))
    generate_cube_vtp('cube.vtp')
    generate_sphere_vtp('sphere.vtp', n_phi=48, n_theta=24)
    generate_torus_vtp('torus_simulation.vtp', R=1.0, r=0.35, n_u=64, n_v=32)
    print('Done!')


if __name__ == '__main__':
    main()
