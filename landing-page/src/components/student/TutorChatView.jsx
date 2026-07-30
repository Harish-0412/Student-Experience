import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  BookOpen,
  Brain,
  ExternalLink,
  MessageSquare,
  Plus,
  Send,
} from 'lucide-react';

const tutorModes = [
  { label: 'Explain', value: 'explain' },
  { label: 'Hint', value: 'hint' },
  { label: 'Quiz', value: 'quiz' },
  { label: 'Debug', value: 'debug' },
];

export const TutorChatView = () => {
  const {
    selectedGoal,
    conversations,
    activeConvId,
    setActiveConvId,
    addTutorMessage,
    tutorBusy,
  } = useApp();
  const [inputText, setInputText] = useState('');
  const [selectedMode, setSelectedMode] = useState('explain');
  const currentConversation =
    conversations.find((item) => item.id === activeConvId) || null;

  const send = async (event) => {
    event.preventDefault();
    const message = inputText.trim();
    if (!message || tutorBusy || !selectedGoal) return;
    setInputText('');
    try {
      await addTutorMessage(currentConversation?.id || null, message, selectedMode);
    } catch {
      setInputText(message);
    }
  };

  if (!selectedGoal) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center text-sm text-gray-500">
        Select a goal before opening a contextual tutor thread.
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-150px)] max-w-7xl flex-col gap-5 pb-6 lg:flex-row">
      <aside className="w-full shrink-0 border-b border-white/10 pb-4 lg:w-72 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-bold text-white">
            <MessageSquare className="h-4 w-4 text-purple-400" />
            Tutor threads
          </h2>
          <button
            type="button"
            onClick={() => setActiveConvId(null)}
            className="rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white"
            title="New thread"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <div className="flex gap-2 overflow-x-auto lg:block lg:space-y-1">
          {conversations.map((conversation) => (
            <button
              type="button"
              key={conversation.id}
              onClick={() => setActiveConvId(conversation.id)}
              className={`w-56 shrink-0 rounded-lg p-3 text-left lg:w-full ${
                conversation.id === activeConvId
                  ? 'bg-purple-500/15 text-white'
                  : 'text-gray-400 hover:bg-white/5'
              }`}
            >
              <div className="truncate text-xs font-bold">
                {conversation.title}
              </div>
              <div className="mt-1 text-[10px] capitalize text-purple-300">
                {conversation.mode} · {conversation.messages.length} messages
              </div>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="py-5 text-xs text-gray-500">No tutor threads yet.</p>
          )}
        </div>
      </aside>

      <section className="flex min-h-[600px] min-w-0 flex-1 flex-col">
        <div className="flex flex-col justify-between gap-3 border-b border-white/10 pb-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-lg font-bold text-white">
              {currentConversation?.title || 'New tutor thread'}
            </h1>
            <p className="mt-1 text-xs text-gray-500">{selectedGoal.title}</p>
          </div>
          <div className="flex gap-1 rounded-lg bg-white/5 p-1">
            {tutorModes.map((mode) => (
              <button
                type="button"
                key={mode.value}
                onClick={() => setSelectedMode(mode.value)}
                className={`rounded-md px-3 py-1.5 text-xs font-bold ${
                  selectedMode === mode.value
                    ? 'bg-purple-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto py-6">
          {currentConversation?.messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.sender === 'student' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.sender === 'tutor' && (
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-purple-500/15 text-purple-300">
                  <Brain className="h-5 w-5" />
                </div>
              )}
              <div
                className={`max-w-2xl rounded-lg p-4 text-sm leading-relaxed ${
                  message.sender === 'student'
                    ? 'bg-purple-600 text-white'
                    : 'border border-white/10 bg-white/5 text-gray-100'
                }`}
              >
                <div className="whitespace-pre-wrap">{message.text}</div>
                {message.citations?.length > 0 && (
                  <div className="mt-4 space-y-2 border-t border-white/10 pt-3">
                    {message.citations.map((citation) => (
                      <a
                        key={citation.resource_id}
                        href={citation.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-start gap-2 text-xs text-purple-300 hover:text-purple-200"
                      >
                        <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>
                          <strong>{citation.title}</strong>
                          <span className="block text-gray-500">
                            {citation.excerpt}
                          </span>
                        </span>
                        <ExternalLink className="mt-0.5 h-3 w-3 shrink-0" />
                      </a>
                    ))}
                  </div>
                )}
                {message.followUpQuestions?.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {message.followUpQuestions.map((question) => (
                      <button
                        type="button"
                        key={question}
                        onClick={() => setInputText(question)}
                        className="rounded-md border border-white/10 px-2 py-1 text-left text-[11px] text-gray-300 hover:bg-white/5"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {!currentConversation && (
            <div className="flex min-h-72 items-center justify-center text-center">
              <div>
                <Brain className="mx-auto h-8 w-8 text-purple-400" />
                <p className="mt-3 text-sm text-gray-400">
                  Start with a question about your selected goal.
                </p>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={send} className="flex gap-3 border-t border-white/10 pt-4">
          <input
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            placeholder={`Ask in ${selectedMode} mode`}
            maxLength={6000}
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
          />
          <button
            type="submit"
            disabled={tutorBusy || !inputText.trim()}
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-5 py-3 text-sm font-bold text-white hover:bg-purple-500 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {tutorBusy ? 'Working...' : 'Send'}
          </button>
        </form>
      </section>
    </div>
  );
};
