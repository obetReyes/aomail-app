/** @type {import('tailwindcss').Config} */
export const darkMode = "class";
export const content = ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"];
export const theme = {
    extend: {
        keyframes: {
            slideIn: {
                "0%": { transform: "translateX(100%)" },
                "100%": { transform: "translateX(0)" },
            },
            slideOut: {
                "0%": { transform: "translateX(0)" },
                "100%": { transform: "translateX(100%)" },
            },
        },
        animation: {
            slideIn: "slideIn 0.5s ease-out forwards",
            slideOut: "slideOut 0.5s ease-out forwards",
        },
    },
};
export const plugins = [require("@tailwindcss/forms")];
