import streamlit as st
from PIL import Image, PngImagePlugin
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
    .main .block-container {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(20px);
        padding: 3rem;
        border-radius: 30px;
    }
    [data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderFileName"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def find_best_divider(img):
    """
    增强型动态检测：
    如果图片没有元数据，通过计算垂直线条的能量分布，找到最像“缝隙”的地方。
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    # 只扫描中间 40% 到 60% 的区域，避免边缘干扰
    start_col, end_col = int(w * 0.4), int(w * 0.6)
    
    # 计算每一列的垂直梯度之和，缝隙处的梯度通常很小
    col_scores = []
    for j in range(start_col, end_col):
        # 计算该列与其左右列的差异
        diff = np.sum(np.abs(arr[:, j].astype(float) - arr[:, j-1].astype(float)))
        col_scores.append(diff)
    
    best_col = start_col + np.argmin(col_scores)
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
        st.info(f"已选中 {len(up_p)} 张")
        c1, c2 = st.columns(2)
        with c1: dir_mode = st.segmented_control("方向", ["左右", "上下"], default="左右")
        with c2: is_align = st.toggle("无痕拼图", value=False)

        if st.button("🚀 开始拼图"):
            sorted_files = sorted(up_p, key=lambda x: 自然排序(x.name))
            status = st.empty(); prog = st.progress(0); buf = io.BytesIO()
            total_pairs = len(sorted_files) // 2
            
            with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    curr = i // 2 + 1
                    status.text(f"拼装中: {curr}/{total_pairs}")
                    img1 = Image.open(sorted_files[i]).convert("RGBA")
                    img2 = Image.open(sorted_files[i+1]).convert("RGBA")
                    
                    if is_align:
                        if dir_mode == "左右拼":
                            th = max(img1.height, img2.height)
                            img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                            img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                        else:
                            tw = max(img1.width, img2.width)
                            img1 = img1.resize((tw, int(img1.height*tw/img1.width)), Image.Resampling.LANCZOS)
                            img2 = img2.resize((tw, int(img2.height*tw/img2.width)), Image.Resampling.LANCZOS)

                    # 记录第一张图的原始尺寸
                    recipe = {"w1": img1.width, "h1": img1.height, "dir": dir_mode}
                    
                    if dir_mode == "左右拼":
                        canvas = Image.new('RGBA', (img1.width+img2.width, img1.height), (0,0,0,0))
                        canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width,0))
                    else:
                        canvas = Image.new('RGBA', (img1.width, img1.height+img2.height), (0,0,0,0))
                        canvas.paste(img1,(0,0)); canvas.paste(img2,(0,img1.height))
                    
                    # 写入元数据 (PngInfo)
                    meta = PngImagePlugin.PngInfo()
                    meta.add_text("recipe", json.dumps(recipe))
                    
                    tmp = io.BytesIO()
                    canvas.save(tmp, format="PNG", pnginfo=meta)
                    zf.writestr(f"Result_{curr}.png", tmp.getvalue())
                    prog.progress((i+2)/(total_pairs*2))
            st.success("完成！")
            st.download_button("📂 下载拼图包", buf.getvalue(), "Export.zip")

# --- 2. 拆图区 ---
with tabs[1]:
    u1, u2 = st.columns([0.8, 0.2])
    u1.markdown("### 1. 上传拼图")
    if u2.button("🧹 一键清空", key="u_clr"):
        st.session_state.u_clear_id += 1
        st.rerun()

    up_u = st.file_uploader("上传图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key=f"u_u_{st.session_state.u_clear_id}")
    
    if up_u:
        if st.button("🔍 智能拆分"):
            status_u = st.empty(); prog_u = st.progress(0); buf_u = io.BytesIO()
            with zipfile.ZipFile(buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(up_u):
                    status_u.text(f"拆分中: {f.name}")
                    img = Image.open(f)
                    
                    # 优先读取元数据：这是最精准的
                    if "recipe" in img.info:
                        r = json.loads(img.info["recipe"])
                        if r["dir"] == "左右":
                            res1 = img.crop((0, 0, r["w1"], img.height))
                            res2 = img.crop((r["w1"], 0, img.width, img.height))
                        else:
                            res1 = img.crop((0, 0, img.width, r["h1"]))
                            res2 = img.crop((0, r["h1"], img.width, img.height))
                    else:
                        # 兜底方案：动态计算分割线
                        # 这里以左右拆分为例（你大部分应该是左右拼）
                        split_pos = find_best_divider(img)
                        res1 = img.crop((0, 0, split_pos, img.height))
                        res2 = img.crop((split_pos, 0, img.width, img.height))
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, "PNG"); res2.save(b2, "PNG")
                    zf.writestr(f"S_{idx}_A.png", b1.getvalue())
                    zf.writestr(f"S_{idx}_B.png", b2.getvalue())
                    prog_u.progress((idx+1)/len(up_u))
            st.success("拆分完毕！")
            st.download_button("📂 下载还原包", buf_u.getvalue(), "Restored.zip")
