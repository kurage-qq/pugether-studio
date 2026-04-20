import streamlit as st
from PIL import Image, ImageChops
import io
import zipfile
import re
import numpy as np

# --- 1. 页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

if 'p_clear_id' not in st.session_state: st.session_state.p_clear_id = 0
if 'u_clear_id' not in st.session_state: st.session_state.u_clear_id = 0

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container { background-color: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); padding: 3rem; border-radius: 30px; }
    [data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderFileName"] { display: none !important; }
    .stButton>button { border-radius: 12px; font-weight: 600; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def smart_white_block_split(img):
    """
    基于白色像素块竖向边界的自动拆分算法
    """
    img_rgba = img.convert("RGBA")
    w, h = img_rgba.size
    # 转换成灰度以便检测“白色”
    gray = img.convert("L")
    arr = np.array(gray)
    
    # 1. 找到每一列的平均亮度（255 为纯白）
    col_means = np.mean(arr, axis=0)
    
    # 2. 定义什么是“白色列”（亮度大于 250 的视为白边/背景）
    is_white_col = col_means > 250
    
    # 3. 在中部 30%-70% 范围内寻找最宽的白色像素块
    mid_start, mid_end = int(w * 0.3), int(w * 0.7)
    
    # 寻找内容结束和开始的竖向边界
    # 我们找中部区域中，第一个出现的白色块起始点，和最后一个白色块结束点
    content_end = mid_start
    content_start = mid_end
    
    # 从左往右找第一张图的边缘
    for j in range(mid_start, mid_end):
        if is_white_col[j]:
            content_end = j
            break
            
    # 从右往左找第二张图的边缘
    for j in range(mid_end, mid_start, -1):
        if is_white_col[j]:
            content_start = j
            break

    # 4. 执行拆分
    # 左图：从 0 到白色块开始的地方
    # 右图：从白色块结束的地方到最后
    part1 = img_rgba.crop((0, 0, content_end, h))
    part2 = img_rgba.crop((content_start, 0, w, h))
    
    # 5. 自动裁掉各自图片内部残留的上下白边（由高度不一引起）
    def final_trim(im):
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        diff = ImageChops.difference(im, bg)
        bbox = diff.getbbox()
        return im.crop(bbox) if bbox else im

    return [final_trim(part1), final_trim(part2)]

# --- 1. 拼图区 ---
with tabs[0]:
    h1, h2 = st.columns([0.8, 0.2])
    h1.markdown("### 1. 上传素材")
    if h2.button("🧹 一键清空", key="p_clr"):
        st.session_state.p_clear_id += 1
        st.rerun()

    up_p = st.file_uploader("图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key=f"p_u_{st.session_state.p_clear_id}")
    
    if up_p:
        st.info(f"已选中 {len(up_p)} 张图片")
        c1, c2 = st.columns(2)
        with c1: dir_mode = st.segmented_control("方向", ["左右拼", "上下拼"], default="左右拼")
        with c2: is_align = st.toggle("🧪 智能拉伸对齐", value=False)

        if st.button("🚀 开始批量拼图", key="p_start_btn"):
            sorted_files = sorted(up_p, key=lambda x: 自然排序(x.name))
            total_pairs = len(sorted_files) // 2
            p_status = st.empty(); p_bar = st.progress(0); zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    p_status.text(f"拼装中: {i//2+1} / {total_pairs}")
                    img1, img2 = Image.open(sorted_files[i]).convert("RGBA"), Image.open(sorted_files[i+1]).convert("RGBA")
                    if is_align:
                        th = max(img1.height, img2.height)
                        img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                        img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                    
                    w_c = img1.width + img2.width if dir_mode == "左右拼" else max(img1.width, img2.width)
                    h_c = max(img1.height, img2.height) if dir_mode == "左右拼" else img1.height + img2.height
                    canvas = Image.new('RGBA', (w_c, h_c), (255, 255, 255, 255))
                    canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width if dir_mode == "左右拼" else 0, 0 if dir_mode == "左右拼" else img1.height))
                    
                    tmp = io.BytesIO(); canvas.save(tmp, format="PNG")
                    zf.writestr(f"Result_{i//2+1}.png", tmp.getvalue())
                    p_bar.progress((i + 2) / (total_pairs * 2))
            st.balloons()
            st.download_button("📂 下载拼图包", zip_buf.getvalue(), "Export.zip")

# --- 2. 拆图区 (竖向边界裁剪版) ---
with tabs[1]:
    u1, u2 = st.columns([0.8, 0.2])
    u1.markdown("### 1. 上传拼图")
    if u2.button("🧹 一键清空", key="u_clr"):
        st.session_state.u_clear_id += 1
        st.rerun()

    up_u = st.file_uploader("图片", type=["png", "jpg"], accept_multiple_files=True, label_visibility="collapsed", key=f"u_u_{st.session_state.u_clear_id}")
    
    if up_u:
        if st.button("🔍 自动检测白块并拆分", key="u_start_btn"):
            u_status = st.empty(); u_bar = st.progress(0); zip_buf_u = io.BytesIO()
            total = len(up_u)
            with zipfile.ZipFile(zip_buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(up_u):
                    u_status.text(f"正在分析边界: {idx+1}/{total}")
                    img = Image.open(f)
                    
                    # 使用“白块竖向边界”算法
                    res_list = smart_white_block_split(img)
                    
                    for sub_idx, res in enumerate(res_list):
                        b = io.BytesIO()
                        res.save(b, "PNG")
                        suffix = "A" if sub_idx == 0 else "B"
                        zf.writestr(f"{f.name}_{suffix}.png", b.getvalue())
                    
                    u_bar.progress((idx + 1) / total)
            
            u_status.success(f"✨ 拆分完成！已自动识别白色区域并裁剪。")
            st.download_button("📂 下载还原包", zip_buf_u.getvalue(), "Restored.zip")
