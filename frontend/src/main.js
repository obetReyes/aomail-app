import { createApp } from 'vue'
import App from './App.vue'
import './assets/css/tailwind.css'
import router from './router';  // Change this line
import axios from 'axios';

// Define the API base URL globally
export const API_BASE_URL = `https://${process.env.VUE_APP_ENV}.aochange.com/MailAssistant/`;

axios.defaults.headers.post['Cross-Origin-Opener-Policy'] = "same-origin-allow-popups";

const app = createApp(App);

app.use(router);

app.mount('#app');