if ("serviceWorker" in navigator) { window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js").catch(console.error)); }
const photoInput=document.querySelector('input[type=file][name=photo]');
if(photoInput){photoInput.addEventListener('change',()=>{const file=photoInput.files?.[0],preview=document.getElementById('preview');if(file&&preview){preview.src=URL.createObjectURL(file);preview.hidden=false;}});}
