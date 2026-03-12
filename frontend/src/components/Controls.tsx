import { useState } from 'react';

interface ControlsProps {
  onDiscover: (phoneNumber: string) => void;
  onStop: () => void;
  onClear: () => void;
  isRunning: boolean;
  hasSession: boolean;
}

export function Controls({ onDiscover, onStop, onClear, isRunning, hasSession }: ControlsProps) {
  const [phoneNumber, setPhoneNumber] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (phoneNumber.trim() && !isRunning) {
      onDiscover(phoneNumber.trim());
    }
  };

  return (
    <div className="flex items-center gap-2">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="tel"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          placeholder="+1 (800) 275-8777"
          className="
            bg-gray-900 border border-gray-700/50 rounded-lg px-4 py-2
            text-sm text-white placeholder-gray-600
            focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20
            w-56 transition-all
          "
          disabled={isRunning}
        />
        <button
          type="submit"
          disabled={!phoneNumber.trim() || isRunning}
          className="
            bg-indigo-600 hover:bg-indigo-500
            disabled:bg-gray-800 disabled:text-gray-600 disabled:border-gray-700
            text-white text-sm font-medium px-5 py-2 rounded-lg
            border border-indigo-500/30 disabled:border-gray-700/50
            transition-all duration-200
          "
        >
          Discover
        </button>
      </form>

      {isRunning && (
        <button
          onClick={onStop}
          className="
            bg-red-950 hover:bg-red-900 text-red-400 hover:text-red-300
            text-sm font-medium px-4 py-2 rounded-lg
            border border-red-500/30
            transition-all duration-200
          "
        >
          Stop
        </button>
      )}

      {hasSession && !isRunning && (
        <button
          onClick={onClear}
          className="
            bg-gray-900 hover:bg-gray-800 text-gray-400 hover:text-gray-300
            text-sm font-medium px-4 py-2 rounded-lg
            border border-gray-700/50
            transition-all duration-200
          "
        >
          Clear
        </button>
      )}
    </div>
  );
}
