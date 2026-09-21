// TODO: functions that call our FastAPI backend, e.g.:
// export async function transcribeAudio(blob) { ... }
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export default API_BASE;