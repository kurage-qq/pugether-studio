import streamlit as st
from PIL import Image, PngImagePlugin, ImageChops
import json
import io
import zipfile
import re
import numpy as np

# --- 页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

if 'p_clear_id' not in st.session_state: st.session_state.p_clear_id = 0
if 'u_clear_id' not in st.session_state: st.session_state.u_clear_id = 0

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container { background-color: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); padding: 3rem; border-radius: 30px; }
    [data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderFileName"] { display: none !important; }
    .stButton>button { border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def trim_borders(img):
    """自动裁切掉图片四周的纯色边框（解决白边/黑边）"""
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

def find_precise_divider(img):
    """高精度动态检测：利用Sobel边缘能量分布定位分割线"""
    arr = np.array(img.convert("L")).astype(float)
    h, w = arr.shape
    
    # 扫描中部 40%-60% 区域
    start_col, end_col = int(w * 0.4), int(w * 0.6)
    
    # 计算水平方向的梯度（找垂直缝隙）
    # 缝隙处的特征是：该列像素与其左右像素差异极大，或者该列本身是极其稳定的纯色
    energy = []
    for j in range(start_col, end_col):
        # 能量计算：考虑当前列的波动以及与相邻列的断层感
        col_energy = np.std(arr[:, j]) + np.abs(np.mean(arr[:, j]) - np.mean(arr[:, j-1]))
        energy.append(col_energy)
    
    # 找到能量变化的“断层点”
    best_col = start_col + np.argmin(energy)
    return best_col

# --- 1. 拼图区 ---
with tabs[0]:
    h1, h2 = st.columns([0.8, 0.2])
    h1.markdown("### 1. 上传素材")
    if h2.button("🧹 一键清空", key="p_clr"):
        st.session_state.p_clear_id += 1
        st.rerun()

    up_p = st.file_uploader("图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key=f"p_u_{st.session_state.p_clear_id}")
    
    if up_p:
        c1, c2 = st.columns(2)
        with c1: dir_mode = st.segmented_control("方向", ["左右", "上下"], default="左右")
        with c2: is_align = st.toggle("无痕对齐", value=False) 

        if st.button("🚀 开始拼图"):
            sorted_files = sorted(up_p, key=lambda x: 自然排序(x.name))
            buf = io.BytesIO()
            total_pairs = len(sorted_files) // 2
            with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    img1, img2 = Image.open(sorted_files[i]).convert("RGBA"), Image.open(sorted_files[i+1]).convert("RGBA")
                    if is_align:
                        if dir_mode == "左右拼":
                            th = max(img1.height, img2.height)
                            img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                            img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                        else:
                            tw = max(img1.width, img2.width)
                            img1 = img1.resize((tw, int(img1.height*tw/img1.width)), Image.Resampling.LANCZOS)
                            img2 = img2.resize((tw, int(img2.height*tw/img2.width)), Image.Resampling.LANCZOS)
                    
                    # 正常拼接（不拉伸时矮的一方会留白，由拆图端解决）
                    w_c = img1.width + img2.width if dir_mode == "左右拼" else max(img1.width, img2.width)
                    h_c = max(img1.height, img2.height) if dir_mode == "左右拼" else img1.height + img2.height
                    canvas = Image.new('RGBA', (w_c, h_c), (255, 255, 255, 255))
                    canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width if dir_mode == "左右拼" else 0, 0 if dir_mode == "左右拼" else img1.height))
                    
                    meta = PngImagePlugin.PngInfo()
                    meta.add_text("recipe", json.dumps({"w1":img1.width, "h1":img1.height, "dir":dir_mode}))
                    tmp = io.BytesIO(); canvas.save(tmp, format="PNG", pnginfo=meta)
                    zf.writestr(f"Result_{i//2+1}.png", tmp.getvalue())
            st.download_button("📂 下载拼图包", buf.getvalue(), "Export.zip")

# --- 2. 拆图区 ---
with tabs[1]:
    u1, u2 = st.columns([0.8, 0.2])
    u1.markdown("### 1. 上传拼图")
    if u2.button("🧹 一键清空", key="u_clr"):
        st.session_state.u_clear_id += 1
        st.rerun()

    up_u = st.file_uploader("图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key=f"u_u_{st.session_state.u_clear_id}")
    
    if up_u:
        if st.button("🔍 智能拆分还原"):
            status_u = st.empty(); prog_u = st.progress(0); buf_u = io.BytesIO()
            with zipfile.ZipFile(buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(up_u):
                    img = Image.open(f).convert("RGBA")
                    # 1. 获取分割线位置
                    if "recipe" in img.info:
                        r = json.loads(img.info["recipe"])
                        pos = r["w1"] if r["dir"] == "左右" else r["h1"]
                        mode = "左右" if r["dir"] == "左右" else "上下"
                    else:
                        pos = find_precise_divider(img)
                        mode = "左右"

                    # 2. 初步拆分
                    if mode == "左右":
                        res1, res2 = img.crop((0, 0, pos, img.height)), img.crop((pos, 0, img.width, img.height))
                    else:
                        res1, res2 = img.crop((0, 0, img.width, pos)), img.crop((0, pos, img.width, img.height))
                    
                    # 3. 【核心增强】自动识别并裁掉拆分后图片里的无效边框/白边
                    res1, res2 = trim_borders(res1), trim_borders(res2)
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, "PNG"); res2.save(b2, "PNG")
                    zf.writestr(f"{f.name}_A.png", b1.getvalue()); zf.writestr(f"{f.name}_B.png", b2.getvalue())
                    prog_u.progress((idx+1)/len(up_u))
            st.success("拆分完成（已自动去除白边）")
            st.download_button("📂 下载还原包", buf_u.getvalue(), "Restored.zip")
