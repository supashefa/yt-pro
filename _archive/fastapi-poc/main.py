from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
import yt_dlp
import os

app = FastAPI()

# Helper function to delete the file
def cleanup_file(path: str):
    if os.path.exists(path):
        os.remove(path)

@app.get("/download")
async def download_video(url: str, background_tasks: BackgroundTasks):
    ydl_opts = {
        'format': 'best',
        'outtmpl': '/tmp/%(title)s.%(ext)s', 
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Schedule the file to be deleted after the response is sent
            background_tasks.add_task(cleanup_file, filename)
            
            return FileResponse(
                path=filename, 
                filename=os.path.basename(filename),
                media_type='video/mp4'
            )
    except Exception as e:
        return {"error": str(e)}