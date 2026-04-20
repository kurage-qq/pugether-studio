import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

# 初始化清空计数器
if 'p_clear_id' not in st.session_state: st.session_state.p_clear_id = 0
if 'u_clear_id' not in st.session_state: st.session_state.u_clear_id = 0

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(20px);
        padding: 3rem;
        border-radius: 30px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.05);
    }
    .stButton>button { border-radius: 12px; font-weight: 600; width: 100%; }
    [data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderFileName"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def find_divider_dynamic(img):
    """动态扫描算法：寻找方差最小的列作为分割线"""
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    search_w = range(int(w*0.3), int(w*0.7))
    best_col, min_var = w//2, float('inf')
    for j in search_w:
        v = np.var(arr[:, j])
        if v < min_var:
            min_var, best_col = v, j
    return best_col

# --- 1. 拼图区 ---
with tabs[0]:
    h1, h2 = st.columns([0.8, 0.2])
    h1.markdown("### 1. 上传素材")
    if h2.button("🧹 一键清空", key="p_clr"):
        st.session_state.p_clear_id += 1
        st.rerun()

    up_p = st.file_uploader("拖入图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key=f"p_u_{st.session_state.p_clear_id}")
    
    if up_p:
        st.info(f"已选中 {len(up_p)} 张图片")
        c1, c2 = st.columns(2)
        with c1: dir_mode = st.segmented_control("方向", ["左右", "上下"], default="左右")
        with c2: is_align = st.toggle("无痕拼图", value=False)

        if st.button("🚀 开始批量拼图", key="p_start"):
            sorted_files = sorted(up_p, key=lambda x: 自然排序(x.name))
            total_pairs = len(sorted_files) // 2
            
            p_status = st.empty(); p_bar = st.progress(0); zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    curr = i // 2 + 1
                    p_status.text(f"正在拼装: {curr}/{total_pairs}")
                    
                    img1 = Image.open(sorted_files[i]).convert("RGBA")
                    img2 = Image.open(sorted_files[i+1]).convert("RGBA")
                    
                    # 记录原始尺寸用于后续精准还原
                    recipe = {"w1": img1.width, "h1": img1.height, "dir": dir_mode}
                    
                    if is_align:
                        if dir_mode == "左右拼":
                            th = max(img1.height, img2.height)
                            img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                            img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                        else:
                            tw = max(img1.width, img2.width)
                            img1 = img1.resize((tw, int(img1.height*tw/img1.width)), Image.Resampling.LANCZOS)
                            img2 = img2.resize((tw, int(img2.height*tw/img2.width)), Image.Resampling.LANCZOS)
                    
                    w_c = img1.width + img2.width if dir_mode == "左右拼" else max(img1.width, img2.width)
                    h_c = max(img1.height, img2.height) if dir_mode == "左右拼" else img1.height + img2.height
                    canvas = Image.new('RGBA', (w_c, h_c), (255, 255, 255, 255))
                    canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width if dir_mode == "左右拼" else 0, 0 if dir_mode == "左右拼" else img1.height))
                    
                    # 写入元数据
                    meta = PngImagePlugin.PngInfo()
                    meta.add_text("recipe", json.dumps(recipe))
                    
                    tmp = io.BytesIO()
                    canvas.save(tmp, format="PNG", pnginfo=meta)
                    zf.writestr(f"Result_{curr}.png", tmp.getvalue())
                    p_bar.progress((i + 2) / (total_pairs * 2))
            
            p_status.success("✨ 拼图完成！")
            st.download_button("📂 下载拼图包", zip_buf.getvalue(), "Pugether_Export.zip")

# --- 2. 拆图区 (复原检测逻辑) ---
with tabs[1]:
    u1, u2 = st.columns([0.8, 0.2])
    u1.markdown("### 1. 上传拼图")
    if u2.button("🧹 一键清空", key="u_clr"):
        st.session_state.u_clear_id += 1
        st.rerun()

    up_u = st.file_uploader("图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key=f"u_u_{st.session_state.u_clear_id}")
    
    if up_u:
        if st.button("🔍 拆分", key="u_start"):
            u_status = st.empty(); u_bar = st.progress(0); zip_buf_u = io.BytesIO()
            total = len(up_u)
            
            with zipfile.ZipFile(zip_buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(up_u):
                    u_status.text(f"正在分析: {idx+1}/{total}")
                    img = Image.open(f)
                    
                    # --- 复原的核心逻辑：优先检测 recipe ---
                    if "recipe" in img.info:
                        r = json.loads(img.info["recipe"])
                        if r["dir"] == "左右":
                            res1 = img.crop((0, 0, r["w1"], img.height))
                            res2 = img.crop((r["w1"], 0, img.width, img.height))
                        else:
                            res1 = img.crop((0, 0, img.width, r["h1"]))
                            res2 = img.crop((0, r["h1"], img.width, img.height))
                    else:
                        # 兜底动态检测
                        pos = find_divider_dynamic(img)
                        res1 = img.crop((0, 0, pos, img.height))
                        res2 = img.crop((pos, 0, img.width, img.height))
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, "PNG"); res2.save(b2, "PNG")
                    zf.writestr(f"{f.name}_A.png", b1.getvalue())
                    zf.writestr(f"{f.name}_B.png", b2.getvalue())
                    u_bar.progress((idx + 1) / total)
            
            u_status.success("✨ 拆分完成！")
            st.download_button("📂 下载", zip_buf_u.getvalue(), "Restored.zip")
