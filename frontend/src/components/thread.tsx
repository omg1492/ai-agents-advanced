import {
  ActionBarPrimitive,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import type { FC } from "react";
import {
  ArrowDownIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  PencilIcon,
  RefreshCwIcon,
  SendHorizontalIcon,
  ChevronDownIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { MarkdownText } from "@/components/markdown-text";
import { TooltipIconButton } from "@/components/tooltip-icon-button";
import { useEffect, useState } from "react";
import { dreamFarmChatAdapter } from '@/services/chatAdapter';

interface ThreadProps { threadId?: string | null }

export const Thread: FC<ThreadProps> = ({ threadId }) => {
  // NOTE: assistant-ui maintains internal state; switching key in parent remounts.
  // We could add future hydration logic here using threadId to fetch history.
  const [historyBlocks, setHistoryBlocks] = useState<any[]>([]);
  const [metaEvents, setMetaEvents] = useState<any[]>([]);
  
  useEffect(() => {
    // Clear when switching (fresh mount already, but ensure)
    setHistoryBlocks([]);
    setMetaEvents([]);
    
    if (!threadId) { return; }
    
    const handler = (e: Event) => {
      const ce = e as CustomEvent;
      if (ce.detail?.threadId !== threadId) return;
      const msgs = ce.detail.messages as any[];
      const mapped = msgs.map(m => ({ role: m.role, content: m.content }));
      setHistoryBlocks(mapped);
    };
    
    const metaClearHandler = () => {
      setMetaEvents([]);
    };
    
    window.addEventListener('df-thread-history', handler as EventListener);
    window.addEventListener('df-meta-clear', metaClearHandler);
    
    // Trigger preload (adapter prevents duplicate work)
    dreamFarmChatAdapter.preloadMessages(threadId);
    
    return () => {
      window.removeEventListener('df-thread-history', handler as EventListener);
      window.removeEventListener('df-meta-clear', metaClearHandler);
    };
  }, [threadId]);
  
  return (
    <ThreadPrimitive.Root
      className="text-foreground bg-background box-border flex h-full flex-col overflow-hidden"
      style={{
        ["--thread-max-width" as string]: "42rem",
      }}
    >
      <ThreadPrimitive.Viewport className="flex h-full flex-col items-center overflow-y-scroll scroll-smooth bg-inherit px-4 pt-8">
        <ThreadWelcome />

        {historyBlocks.length > 0 && (
          <div className="w-full max-w-[var(--thread-max-width)] flex flex-col gap-2 mb-4">
            {historyBlocks.map((m, i) => (
              <div key={i} className={`rounded-3xl px-5 py-2.5 text-sm whitespace-pre-wrap break-words ${m.role === 'user' ? 'self-end bg-muted' : 'self-start bg-primary/10'}`}>{m.content}</div>
            ))}
            <div className="h-px bg-border my-2" />
          </div>
        )}
        <ThreadPrimitive.Messages
          components={{
            UserMessage: UserMessage,
            EditComposer: EditComposer,
            AssistantMessage: () => <AssistantMessage metaEvents={metaEvents} setMetaEvents={setMetaEvents} />,
          }}
        />

        <ThreadPrimitive.If empty={false}>
          <div className="min-h-8 flex-grow" />
        </ThreadPrimitive.If>

        <div className="sticky bottom-0 mt-3 flex w-full max-w-[var(--thread-max-width)] flex-col items-center justify-end rounded-t-lg bg-inherit pb-4">
          <ThreadScrollToBottom />
          <Composer />
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="absolute -top-8 rounded-full disabled:invisible"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const ThreadWelcome: FC = () => {
  return (
    <ThreadPrimitive.Empty>
      <div className="flex w-full max-w-[var(--thread-max-width)] flex-grow flex-col">
        <div className="flex w-full flex-grow flex-col items-center justify-center">
          <p className="mt-4 font-medium">
            Welcome to Dream Farm! How can I help you today?
          </p>
          <p className="text-muted-foreground mt-2 text-sm">
            Ask me about fresh produce, local farmers, or marketplace services.
          </p>
        </div>
        <ThreadWelcomeSuggestions />
      </div>
    </ThreadPrimitive.Empty>
  );
};

const ThreadWelcomeSuggestions: FC = () => {
  return (
    <div className="mt-3 flex w-full items-stretch justify-center gap-4">
      <ThreadPrimitive.Suggestion
        className="hover:bg-muted/80 flex max-w-sm grow basis-0 flex-col items-center justify-center rounded-lg border p-3 transition-colors ease-in"
        prompt="What fresh produce do you have available?"
        method="replace"
        autoSend
      >
        <span className="line-clamp-2 text-ellipsis text-sm font-semibold">
          What fresh produce do you have available?
        </span>
      </ThreadPrimitive.Suggestion>
      <ThreadPrimitive.Suggestion
        className="hover:bg-muted/80 flex max-w-sm grow basis-0 flex-col items-center justify-center rounded-lg border p-3 transition-colors ease-in"
        prompt="How can I contact local farmers?"
        method="replace"
        autoSend
      >
        <span className="line-clamp-2 text-ellipsis text-sm font-semibold">
          How can I contact local farmers?
        </span>
      </ThreadPrimitive.Suggestion>
      <ThreadPrimitive.Suggestion
        className="hover:bg-muted/80 flex max-w-sm grow basis-0 flex-col items-center justify-center rounded-lg border p-3 transition-colors ease-in"
        prompt="Tell me about seasonal farming practices"
        method="replace"
        autoSend
      >
        <span className="line-clamp-2 text-ellipsis text-sm font-semibold">
          Tell me about seasonal farming practices
        </span>
      </ThreadPrimitive.Suggestion>
    </div>
  );
};

const Composer: FC = () => {
  return (
    <ComposerPrimitive.Root className="focus-within:border-ring/20 flex w-full flex-wrap items-end rounded-lg border bg-inherit px-2.5 shadow-sm transition-colors ease-in">
      <ComposerPrimitive.Input
        key={Math.random().toString(36).slice(2)}
        rows={1}
        autoFocus
        placeholder="Write a message..."
        className="placeholder:text-muted-foreground max-h-40 flex-grow resize-none border-none bg-transparent px-2 py-4 text-sm outline-none focus:ring-0 disabled:cursor-not-allowed"
      />
      <ComposerAction />
    </ComposerPrimitive.Root>
  );
};

const ComposerAction: FC = () => {
  return (
    <>
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            tooltip="Send"
            variant="default"
            className="my-2.5 size-8 p-2 transition-opacity ease-in"
          >
            <SendHorizontalIcon />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel asChild>
          <TooltipIconButton
            tooltip="Cancel"
            variant="default"
            className="my-2.5 size-8 p-2 transition-opacity ease-in"
          >
            <CircleStopIcon />
          </TooltipIconButton>
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="grid auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] gap-y-2 [&:where(>*)]:col-start-2 w-full max-w-[var(--thread-max-width)] py-4">
      <UserActionBar />

      <div className="bg-muted text-foreground max-w-[calc(var(--thread-max-width)*0.8)] break-words rounded-3xl px-5 py-2.5 col-start-2 row-start-2">
        <MessagePrimitive.Parts />
      </div>

      <BranchPicker className="col-span-full col-start-1 row-start-3 -mr-1 justify-end" />
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="flex flex-col items-end col-start-1 row-start-2 mr-3 mt-2.5"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="Edit">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <ComposerPrimitive.Root className="bg-muted my-4 flex w-full max-w-[var(--thread-max-width)] flex-col gap-2 rounded-xl">
      <ComposerPrimitive.Input className="text-foreground flex h-8 w-full resize-none bg-transparent p-4 pb-0 outline-none" />

      <div className="mx-3 mb-3 flex items-center justify-center gap-2 self-end">
        <ComposerPrimitive.Cancel asChild>
          <Button variant="ghost">Cancel</Button>
        </ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send asChild>
          <Button>Send</Button>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
};

const AssistantMessage: FC<{ metaEvents?: any[], setMetaEvents?: React.Dispatch<React.SetStateAction<any[]>> }> = ({ metaEvents = [], setMetaEvents }) => {
  const [metaExpanded, setMetaExpanded] = useState<boolean>(true);
  const [metaContainerEl, setMetaContainerEl] = useState<HTMLDivElement | null>(null);
  
  useEffect(() => {
    if (!setMetaEvents) return;
    const handler = (e: Event) => {
      const ce = e as CustomEvent;
      setMetaEvents((prev) => [...prev, ce.detail]);
    };
    window.addEventListener("df-meta", handler as EventListener);
    return () => window.removeEventListener("df-meta", handler as EventListener);
  }, [setMetaEvents]);
  
  // Auto-scroll to bottom so newest ~5 events remain visible
  useEffect(() => {
    if (metaExpanded && metaContainerEl) {
      metaContainerEl.scrollTop = metaContainerEl.scrollHeight;
    }
  }, [metaEvents, metaExpanded, metaContainerEl]);
  
  return (
    <MessagePrimitive.Root className="grid grid-cols-[auto_auto_1fr] grid-rows-[auto_1fr] relative w-full max-w-[var(--thread-max-width)] py-4">
      <div className="text-foreground max-w-[calc(var(--thread-max-width)*0.8)] break-words leading-7 col-span-2 col-start-2 row-start-1 my-1.5">
        {metaEvents.length > 0 && (
          <div className="mb-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="font-semibold">Activity</div>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded-md border px-2 py-1 hover:bg-muted/60"
                onClick={() => setMetaExpanded((v) => !v)}
                aria-expanded={metaExpanded}
                aria-label={metaExpanded ? 'Hide activity' : 'Show activity'}
              >
                <ChevronDownIcon className={`transition-transform ${metaExpanded ? '' : '-rotate-90'}`} size={14} />
                {metaExpanded ? 'Hide' : 'Show'} ({metaEvents.length})
              </button>
            </div>
            {metaExpanded && (
              <div
                ref={setMetaContainerEl}
                className="mt-2 space-y-1 text-xs text-muted-foreground border rounded-md bg-muted/30 p-2 max-h-48 overflow-y-auto"
              >
                {metaEvents.map((m, idx) => {
                  const isReasoning = m?.kind === 'reasoning';
                  const toolName = m?.tool_name || m?.name;
                  const serverLabel = m?.server_label;
                  const title = isReasoning
                    ? 'Thinking'
                    : toolName
                      ? `Tool: ${toolName}${serverLabel ? ` (${serverLabel})` : ''}`
                      : 'Tool event';
                  const body = typeof m === 'string' ? m : JSON.stringify(m);
                  return (
                    <div key={idx} className="border rounded-md p-2 bg-muted/50">
                      <div className="font-medium">{title}</div>
                      <pre className="whitespace-pre-wrap break-words">{body}</pre>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
        <MessageError />
      </div>

      <AssistantActionBar />

      <BranchPicker className="col-start-2 row-start-2 -ml-2 mr-2" />
    </MessagePrimitive.Root>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="border-destructive bg-destructive/10 dark:text-red-200 dark:bg-destructive/5 text-destructive mt-2 rounded-md border p-3 text-sm">
        <ErrorPrimitive.Message className="line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="text-muted-foreground flex gap-1 col-start-3 row-start-2 -ml-1 data-[floating]:bg-background data-[floating]:absolute data-[floating]:rounded-md data-[floating]:border data-[floating]:p-1 data-[floating]:shadow-sm"
    >
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <MessagePrimitive.If copied>
            <CheckIcon />
          </MessagePrimitive.If>
          <MessagePrimitive.If copied={false}>
            <CopyIcon />
          </MessagePrimitive.If>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip="Refresh">
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
    </ActionBarPrimitive.Root>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn("text-muted-foreground inline-flex items-center text-xs", className)}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};

const CircleStopIcon = () => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      width="16"
      height="16"
    >
      <rect width="10" height="10" x="3" y="3" rx="2" />
    </svg>
  );
};
