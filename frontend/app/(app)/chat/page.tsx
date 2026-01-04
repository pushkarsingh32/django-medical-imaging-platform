'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Send, StopCircle, Copy, CheckCircle, ArrowDown, Database, Bot, User } from 'lucide-react';
import LoadingDots from '@/components/LoadingDots';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiClient } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  toolOutputs?: ToolOutput[];
}

interface ToolCall {
  name: string;
  args: Record<string, any>;
}

interface ToolOutput {
  name: string;
  output: any;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [showScrollDownButton, setShowScrollDownButton] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const examplePrompts = [
    "How many patients are there?",
    "Show me all female patients",
    "List all CT scans",
    "What are the statistics?",
  ];

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '56px';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = Math.min(scrollHeight, 200) + 'px';
    }
  }, [input]);

  // Check if near bottom
  const isNearBottom = useCallback(() => {
    if (!scrollContainerRef.current) return true;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    return scrollHeight - scrollTop - clientHeight <= 100;
  }, []);

  // Handle scroll
  const handleScroll = useCallback(() => {
    if (isNearBottom()) {
      setShowScrollDownButton(false);
    } else {
      setShowScrollDownButton(true);
    }
  }, [isNearBottom]);

  // Auto-scroll only when loading completes
  const prevLoadingRef = useRef(isLoading);
  useEffect(() => {
    if (prevLoadingRef.current && !isLoading) {
      // Loading just finished
      if (scrollContainerRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
        const isNear = scrollHeight - scrollTop - clientHeight <= 100;
        if (isNear) {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }
    prevLoadingRef.current = isLoading;
  }, [isLoading]);

  const handleScrollDownClick = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollDownButton(false);
  };

  const handleCopyMessage = async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setIsLoading(true);

    // Add user message to chat
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);

    try {
      // Use centralized API client with all configuration (credentials, CSRF, correlation ID)
      const response = await apiClient.streamPost('/ai/chat/stream/', {
        message: userMessage,
        history: messages.map((m) => ({
          role: m.role,
          content: m.content,
        })),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      // Handle streaming response
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();
      let assistantMessage: Message = {
        role: 'assistant',
        content: '',
        toolCalls: [],
        toolOutputs: []
      };
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue;

          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'content') {
              assistantMessage.content += data.content;
              setMessages((prev) => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant') {
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                } else {
                  newMessages.push({ ...assistantMessage });
                }
                return newMessages;
              });
            } else if (data.type === 'tool_call') {
              assistantMessage.toolCalls = [...(assistantMessage.toolCalls || []), { name: data.name, args: data.args }];
              setMessages((prev) => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant') {
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                } else {
                  newMessages.push({ ...assistantMessage });
                }
                return newMessages;
              });
            } else if (data.type === 'tool_output') {
              assistantMessage.toolOutputs = [...(assistantMessage.toolOutputs || []), { name: data.name, output: data.output }];
              setMessages((prev) => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant') {
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                } else {
                  newMessages.push({ ...assistantMessage });
                }
                return newMessages;
              });
            } else if (data.type === 'done') {
              setMessages((prev) => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant') {
                  newMessages[newMessages.length - 1] = { ...assistantMessage };
                } else {
                  newMessages.push({ ...assistantMessage });
                }
                return newMessages;
              });
            } else if (data.type === 'error') {
              console.error('Stream error:', data.message);
            }
          } catch (err) {
            console.error('Error parsing SSE data:', err);
          }
        }
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExampleClick = (example: string) => {
    setInput(example);
    textareaRef.current?.focus();
  };

  const hasConversationStarted = messages.length > 0;

  if (!hasConversationStarted) {
    return (
      <div className="container mx-auto p-6 h-[calc(100vh-4rem)] max-w-5xl flex flex-col">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Database Assistant</h1>
            <p className="text-sm text-muted-foreground">
              Ask questions about patients, hospitals, and imaging studies in natural language
            </p>
          </div>
        </div>

        {/* Empty State */}
        <div className="flex flex-1 flex-col items-center justify-center gap-6 rounded-lg border bg-card p-8">
          <div className="text-center">
            <h2 className="mb-2 text-xl font-semibold">
              Start a conversation
            </h2>
            <p className="text-sm text-muted-foreground">
              Try one of these example prompts or type your own question
            </p>
          </div>

          <div className="w-full max-w-xl">
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <div className="flex-1">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      if (input && input.trim().length > 0 && !isLoading) {
                        handleSubmit(e);
                      }
                    }
                  }}
                  placeholder="Ask a question about the database..."
                  className="w-full resize-none rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary overflow-hidden"
                  style={{ minHeight: "56px", maxHeight: "200px" }}
                  rows={1}
                  disabled={isLoading}
                />
              </div>
              <Button
                type="submit"
                size="icon"
                className="h-[56px] w-[56px] shrink-0 rounded-full"
                disabled={isLoading || !input.trim()}
              >
                <Send className="h-5 w-5" />
              </Button>
            </form>
          </div>

          <div className="grid w-full max-w-2xl gap-2 sm:grid-cols-2 mt-4">
            {examplePrompts.map((prompt, index) => (
              <button
                key={index}
                onClick={() => handleExampleClick(prompt)}
                disabled={isLoading}
                className="rounded-lg border bg-background p-4 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {prompt}
              </button>
            ))}
          </div>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            AI can make mistakes. Please verify important information.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 pt-6 h-[calc(100vh-4rem)] max-w-5xl flex flex-col">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Database Assistant</h1>
          <p className="text-sm text-muted-foreground">
            Ask questions about patients, hospitals, and imaging studies in natural language
          </p>
        </div>
      </div>

      {/* Chat Container with absolute positioning - takes remaining space */}
      <div className="relative flex-1 rounded-lg border bg-card overflow-hidden mb-0">
        {/* Messages Area - absolutely positioned */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="absolute top-0 left-0 right-0 bottom-[84px] overflow-y-auto p-4 space-y-4"
        >
          {messages.map((message, index) => (
            <div
              key={index}
              className={cn(
                "flex gap-3",
                message.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {message.role === "assistant" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div
                className={cn(
                  "group relative max-w-[80%] rounded-lg px-4 py-3 text-sm",
                  message.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                )}
              >
                {/* Tool calls */}
                {message.toolCalls && message.toolCalls.length > 0 && (
                  <div className="mb-2 space-y-1">
                    {message.toolCalls.map((tool, toolIdx) => (
                      <div
                        key={toolIdx}
                        className="text-xs bg-background/50 rounded px-2 py-1 flex items-center gap-1"
                      >
                        <Database className="h-3 w-3" />
                        <span className="font-mono">
                          {tool.name}({Object.keys(tool.args).length > 0 ? '...' : ''})
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Message content */}
                {message.content && (
                  <div className="prose prose-xs dark:prose-invert max-w-none break-words">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        // Custom styling for markdown elements
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc ml-4 mb-2">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal ml-4 mb-2">{children}</ol>,
                        li: ({ children }) => <li className="mb-1">{children}</li>,
                        strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                        em: ({ children }) => <em className="italic">{children}</em>,
                        code: ({ children, ...props }) => {
                          const inline = 'inline' in props ? props.inline : false;
                          return inline ? (
                            <code className="bg-gray-200 dark:bg-gray-700 px-1 py-0.5 rounded text-xs font-mono">
                              {children}
                            </code>
                          ) : (
                            <code className="block bg-gray-200 dark:bg-gray-700 p-2 rounded text-xs font-mono overflow-x-auto">
                              {children}
                            </code>
                          );
                        },
                        pre: ({ children }) => <pre className="mb-2">{children}</pre>,
                        h1: ({ children }) => <h1 className="text-xl font-bold mb-2">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-lg font-bold mb-2">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-base font-bold mb-2">{children}</h3>,
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic">
                            {children}
                          </blockquote>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto mb-2">
                            <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600">
                              {children}
                            </table>
                          </div>
                        ),
                        th: ({ children }) => (
                          <th className="border border-gray-300 dark:border-gray-600 px-2 py-1 bg-gray-100 dark:bg-gray-800 font-bold">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-gray-300 dark:border-gray-600 px-2 py-1">
                            {children}
                          </td>
                        ),
                        a: ({ children, href }) => (
                          <a href={href} className="text-blue-500 hover:underline" target="_blank" rel="noopener noreferrer">
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                )}

                {/* Tool outputs (debug view) */}
                {message.toolOutputs && message.toolOutputs.length > 0 && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      View tool outputs ({message.toolOutputs.length})
                    </summary>
                    <div className="mt-1 space-y-1">
                      {message.toolOutputs.map((output, outIdx) => (
                        <div
                          key={outIdx}
                          className="bg-background/50 rounded px-2 py-1 font-mono overflow-auto max-h-32"
                        >
                          <div className="font-bold">{output.name}:</div>
                          <pre className="text-xs whitespace-pre-wrap">
                            {JSON.stringify(output.output, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* Copy button for AI messages */}
                {message.role === "assistant" && message.content && (
                  <button
                    onClick={() => handleCopyMessage(`msg-${index}`, message.content)}
                    className="absolute -right-2 -top-2 rounded-md bg-white dark:bg-gray-700 p-1.5 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 border border-gray-200 dark:border-gray-600"
                  >
                    {copiedMessageId === `msg-${index}` ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                    )}
                  </button>
                )}
              </div>

              {message.role === "user" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500 text-xs font-semibold text-white">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center rounded-lg bg-muted px-4 py-3">
                <LoadingDots className="text-gray-600 dark:text-gray-400" />
                <span className="ml-3 text-sm text-muted-foreground">Thinking</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Scroll to bottom button */}
        {showScrollDownButton && (
          <div className="absolute bottom-24 right-8 z-10">
            <Button
              variant="secondary"
              size="icon"
              className="rounded-full shadow-lg"
              onClick={handleScrollDownClick}
            >
              <ArrowDown className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Input Area - absolutely positioned at bottom with fixed height */}
        <div className="absolute bottom-0 left-0 right-0 h-[84px] border-t bg-background flex flex-col justify-center px-4">
          <form
            onSubmit={handleSubmit}
            className="flex items-end gap-2 w-full"
          >
            <div className="flex-1">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (input && input.trim().length > 0 && !isLoading) {
                      handleSubmit(e);
                    }
                  }
                }}
                placeholder="Ask a question about the database... (Shift + Enter for new line)"
                className="w-full resize-none rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary overflow-hidden"
                style={{ minHeight: "56px", maxHeight: "200px" }}
                rows={1}
                disabled={isLoading}
              />
            </div>

            {isLoading ? (
              <Button
                type="button"
                onClick={() => {}}
                size="icon"
                className="h-[56px] w-[56px] shrink-0 rounded-full"
                variant="destructive"
              >
                <StopCircle className="h-5 w-5" />
              </Button>
            ) : (
              <Button
                type="submit"
                size="icon"
                className="h-[56px] w-[56px] shrink-0 rounded-full"
                disabled={isLoading || !input.trim()}
              >
                <Send className="h-5 w-5" />
              </Button>
            )}
          </form>

          <p className="text-center text-xs text-muted-foreground mt-1">
            AI can make mistakes. Please verify important information.
          </p>
        </div>
      </div>
    </div>
  );
}
