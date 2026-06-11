import React, { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';

const ThemeToggle = () => {
    const [theme, setTheme] = useState('light');

    // On mount, read the preferred theme from localStorage or system preference
    useEffect(() => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            setTheme(savedTheme);
            if (savedTheme === 'dark') {
                document.documentElement.classList.add('dark');
            }
        } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            setTheme('dark');
            document.documentElement.classList.add('dark');
        }
    }, []);

    const toggleTheme = () => {
        if (theme === 'light') {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
            setTheme('dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
            setTheme('light');
        }
    };

    return (
        <button
            onClick={toggleTheme}
            className={`
        relative inline-flex items-center justify-center p-2 rounded-full 
        transition-all duration-300 ease-in-out
        ${theme === 'light'
                    ? 'bg-slate-100 text-amber-500 hover:bg-slate-200'
                    : 'bg-slate-800 text-blue-400 hover:bg-slate-700 hover:shadow-[0_0_15px_rgba(59,130,246,0.5)]'}
      `}
            aria-label="Toggle Dark Mode"
        >
            <div className="relative w-5 h-5 flex items-center justify-center">
                <Sun
                    className={`absolute transition-all duration-500 transform ${theme === 'light' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'
                        }`}
                    size={20}
                />
                <Moon
                    className={`absolute transition-all duration-500 transform ${theme === 'dark' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 rotate-90 scale-50'
                        }`}
                    size={20}
                />
            </div>
        </button>
    );
};

export default ThemeToggle;
