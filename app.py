import os
import time
import threading
import uuid
from flask import Flask, render_template_string, request, jsonify, send_from_directory
import yt_dlp

app = Flask(__name__)

# مجلد التخزين المؤقت للفيديوهات على سيرفر Render
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

active_links = {}

def delete_file_after_delay(file_id, file_path, delay=14400):
    """تدمير الملف وإبطال الرابط تلقائياً بعد مرور 4 ساعات للحفاظ على مساحة السيرفر"""
    time.sleep(delay)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[نظام الأمان]: تم حذف الملف المؤقت بنجاح.")
        except Exception as e:
            print(f"[خطأ]: تعذر حذف الملف: {e}")
    if file_id in active_links:
        del active_links[file_id]

# واجهة المستخدم الاحترافية المتوافقة مع Render وتخطي الحجب
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>موقع التحميل الآمن والسريع - نسخة Render</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a2e; color: #fff; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: #162447; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); width: 100%; max-width: 600px; text-align: center; }
        h1 { color: #e43f5a; margin-bottom: 20px; font-size: 26px; }
        p { color: #cbd5e1; font-size: 15px; line-height: 1.6; }
        input[type="text"], select { width: 100%; padding: 14px; margin: 15px 0; border: 2px solid #1f4068; border-radius: 8px; box-sizing: border-box; font-size: 16px; background: #1f4068; color: #fff; }
        input[type="text"] { text-align: left; }
        input[type="text"]::placeholder { color: #94a3b8; text-align: right; }
        select { cursor: pointer; text-align: right; }
        button { background-color: #e43f5a; color: white; padding: 14px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; width: 100%; transition: background 0.3s; font-weight: bold; margin-bottom: 10px; }
        button:hover { background-color: #b33046; }
        .btn-success { background-color: #2ecc71; }
        .btn-success:hover { background-color: #27ae60; }
        .result { margin-top: 25px; text-align: right; }
        .video-title { font-weight: bold; color: #e43f5a; margin-bottom: 15px; font-size: 18px; text-align: center; line-height: 1.4; }
        .download-card { background: #1f4068; border: 1px solid #162447; padding: 15px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .download-btn { background-color: #3498db; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: bold; }
        .download-btn:hover { background-color: #2980b9; }
        .loading { display: none; color: #f1c40f; margin-top: 15px; font-weight: bold; font-size: 14px; }
        .note { color: #ff9f43; font-size: 13px; margin-top: 15px; display: block; text-align: center; border-top: 1px dashed #1f4068; padding-top: 10px; }
        #qualitySection { display: none; margin-top: 20px; border-top: 1px solid #1f4068; padding-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>التحميل السريع والآمن ⏳</h1>
        <p>ضع رابط الفيديو لفحص الجودات المتوفرة وتحميلها عبر السيرفر الخاص بك</p>
        
        <input type="text" id="videoUrl" placeholder="أدخل رابط الفيديو هنا...">
        <button id="checkBtn" onclick="checkVideo()">1. فحص الرابط واستخراج الجودات</button>
        
        <div id="loading" class="loading">⏳ جاري فحص الرابط وتخطي الحجب... يرجى الانتظار ثوانٍ.</div>
        
        <div id="qualitySection">
            <div id="vTitle" class="video-title"></div>
            <label for="qualitySelect">اختر الجودة المطلوبة:</label>
            <select id="qualitySelect"></select>
            <button class="btn-success" onclick="downloadVideo()">2. بدء المعالجة والتحميل</button>
        </div>
        
        <div id="result" class="result"></div>
    </div>

    <script>
        let currentUrl = "";

        async function checkVideo() {
            const url = document.getElementById('videoUrl').value;
            const loadingDiv = document.getElementById('loading');
            const qualitySection = document.getElementById('qualitySection');
            const qualitySelect = document.getElementById('qualitySelect');
            const vTitle = document.getElementById('vTitle');
            const resultDiv = document.getElementById('result');
            
            if (!url) { alert('من فضلك ضع رابطاً أولاً'); return; }
            
            currentUrl = url;
            resultDiv.innerHTML = '';
            qualitySection.style.display = 'none';
            loadingDiv.style.display = 'block';
            
            try {
                const response = await fetch('/get_qualities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                loadingDiv.style.display = 'none';
                
                if (data.error) {
                    alert('خطأ: تعذر جلب جودات هذا الرابط، تأكد من سلامته وحاول مجدداً.');
                    return;
                }
                
                vTitle.innerHTML = `🎥 ${data.title}`;
                qualitySelect.innerHTML = '';
                
                data.formats.forEach(f => {
                    const option = document.createElement('option');
                    option.value = f.id;
                    option.text = `${f.resolution} (${f.ext}) ${f.note ? '- ' + f.note : ''}`;
                    qualitySelect.appendChild(option);
                });
                
                qualitySection.style.display = 'block';
            } catch (err) {
                loadingDiv.style.display = 'none';
                alert('حدث خطأ أثناء الاتصال بالخادم.');
            }
        }

        async function downloadVideo() {
            const qualitySelect = document.getElementById('qualitySelect');
            const formatId = qualitySelect.value;
            const resultDiv = document.getElementById('result');
            const loadingDiv = document.getElementById('loading');
            
            resultDiv.innerHTML = '';
            loadingDiv.innerHTML = "⏳ جاري تحميل وتجميع الفيديو على السيرفر... يرجى الانتظار وعدم إغلاق الصفحة.";
            loadingDiv.style.display = 'block';
            
            try {
                const response = await fetch('/download_selected', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: currentUrl, format_id: formatId })
                });
                const data = await response.json();
                loadingDiv.style.display = 'none';
                
                if (data.error) {
                    resultDiv.innerHTML = `<p style="color: #e43f5a; text-align:center; font-weight:bold;">خطأ: فشل تجميع هذه الجودة.</p>`;
                    return;
                }
                
                resultDiv.innerHTML = `
                    <div class="download-card">
                        <span>الجودة المطلوبة جاهزة تماماً للتحميل</span>
                        <a href="${data.download_url}" target="_blank" class="download-btn">تحميل الملف لجهازك 🚀</a>
                    </div>
                    <span class="note">⚠️ سيتم تدمير هذا الملف وإبطال الرابط تلقائياً بعد 4 ساعات لحماية المساحة.</span>
                `;
            } catch (err) {
                loadingDiv.style.display = 'none';
                resultDiv.innerHTML = '<p style="color: #e43f5a; text-align:center;">حدث خطأ في الاتصال بالخادم</p>';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_qualities', methods=['POST'])
def get_qualities():
    data = request.get_json()
    video_url = data.get('url')
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'check_certificates': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://www.google.com/',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_title = info.get('title', 'فيديو مؤقت')
            
            formats_list = []
            seen_resolutions = set()
            
            for f in info.get('formats', []):
                res = f.get('format_note') or f.get('resolution')
                if res and res not in seen_resolutions:
                    if f.get('vcodec') != 'none':
                        seen_resolutions.add(res)
                        formats_list.append({
                            'id': f.get('format_id'),
                            'resolution': res,
                            'ext': f.get('ext', 'mp4'),
                            'note': f.get('filesize_approx') or f.get('filesize') or ''
                        })
            
            if not formats_list:
                formats_list.append({'id': 'best', 'resolution': 'أعلى جودة تلقائية', 'ext': 'mp4', 'note': ''})
                
            return jsonify({'title': video_title, 'formats': formats_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download_selected', methods=['POST'])
def download_selected():
    data = request.get_json()
    video_url = data.get('url')
    format_id = data.get('format_id')
    
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")
    selected_format = f"{format_id}+bestaudio/best"
    
    ydl_opts = {
        'format': selected_format,
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4', 
        'check_certificates': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            actual_filename = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
            if not os.path.exists(actual_filename):
                actual_filename = ydl.prepare_filename(info)
                
            base_filename = os.path.basename(actual_filename)
            active_links[file_id] = base_filename
            download_url = f"/get_file/{file_id}"
            
            threading.Thread(target=delete_file_after_delay, args=(file_id, actual_filename, 14400)).start()
            
            return jsonify({'download_url': download_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get_file/<file_id>')
def get_file(file_id):
    if file_id in active_links:
        filename = active_links[file_id]
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    else:
        return "<h1>عذراً، هذا الرابط انتهت صلاحيته الزمنيّة! ⏳</h1>", 404

if __name__ == '__main__':
    # قراءة بورت السيرفر ديناميكياً لتفادي مشاكل توقف Render المعتادة
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
