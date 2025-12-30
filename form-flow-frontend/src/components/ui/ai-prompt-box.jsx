import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { ArrowUp, Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/context/ThemeProvider";

const Textarea = React.forwardRef(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      "flex w-full rounded-md border-none bg-transparent px-3 py-2.5 text-base text-white dark:text-zinc-900 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none !outline-none focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] resize-none",
      className
    )}
    ref={ref}
    rows={1}
    {...props}
  />
));
Textarea.displayName = "Textarea";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = React.forwardRef(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-md border border-zinc-200 dark:border-[#333333] bg-white dark:bg-[#1F2023] px-3 py-1.5 text-sm text-zinc-900 dark:text-white shadow-md",
      className
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

const PromptInputContext = React.createContext({
  isLoading: false,
  value: "",
  setValue: () => { },
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
});

function usePromptInput() {
  const context = React.useContext(PromptInputContext);
  if (!context) throw new Error("usePromptInput must be used within a PromptInput");
  return context;
}

const PromptInput = React.forwardRef(
  ({ className, style, isLoading = false, maxHeight = 240, value, onValueChange, onSubmit, children, disabled = false }, ref) => {
    const [internalValue, setInternalValue] = React.useState(value || "");
    const handleChange = (newValue) => {
      setInternalValue(newValue);
      onValueChange?.(newValue);
    };
    return (
      <TooltipProvider>
        <PromptInputContext.Provider
          value={{
            isLoading,
            value: value ?? internalValue,
            setValue: onValueChange ?? handleChange,
            maxHeight,
            onSubmit,
            disabled,
          }}
        >
          <div
            ref={ref}
            className={cn(
              "rounded-3xl border border-zinc-700 dark:border-zinc-300 p-2 shadow-xl shadow-zinc-900/30 dark:shadow-zinc-200/50 transition-all duration-300",
              className
            )}
            style={style}
          >
            {children}
          </div>
        </PromptInputContext.Provider>
      </TooltipProvider>
    );
  }
);
PromptInput.displayName = "PromptInput";

const PromptInputTextarea = ({ className, onKeyDown, disableAutosize = false, placeholder, ...props }) => {
  const { value, setValue, maxHeight, onSubmit, disabled } = usePromptInput();
  const { isDark } = useTheme();
  const textareaRef = React.useRef(null);

  React.useEffect(() => {
    if (disableAutosize || !textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height =
      typeof maxHeight === "number"
        ? `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
        : `min(${textareaRef.current.scrollHeight}px, ${maxHeight})`;
  }, [value, maxHeight, disableAutosize]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
    onKeyDown?.(e);
  };

  // Light mode (black bg) = white text; Dark mode (white bg) = dark text
  const textColor = isDark ? '#18181b' : '#ffffff';
  const placeholderColor = isDark ? '#71717a' : '#a1a1aa';

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      className={cn(
        "prompt-input-textarea flex w-full rounded-md border-none bg-transparent px-3 py-2.5 text-base focus:outline-none !outline-none focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] resize-none",
        className
      )}
      style={{
        color: textColor,
        '--placeholder-color': placeholderColor,
      }}
      disabled={disabled}
      placeholder={placeholder}
      {...props}
    />
  );
};

const PromptInputActions = ({ children, className, ...props }) => (
  <div className={cn("flex items-center gap-2", className)} {...props}>
    {children}
  </div>
);

const PromptInputAction = ({ tooltip, children, className, side = "top", ...props }) => {
  const { disabled } = usePromptInput();
  return (
    <Tooltip {...props}>
      <TooltipTrigger asChild disabled={disabled}>
        {children}
      </TooltipTrigger>
      <TooltipContent side={side} className={className}>
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
};

const Button = React.forwardRef(({ className, variant = "default", size = "default", ...props }, ref) => {
  const variantClasses = {
    default: "bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-white dark:hover:bg-white/80 dark:text-black",
    outline: "border border-zinc-200 dark:border-[#444444] bg-transparent hover:bg-zinc-100 dark:hover:bg-[#3A3A40]",
    ghost: "bg-transparent hover:bg-zinc-100 dark:hover:bg-[#3A3A40]",
  };
  const sizeClasses = {
    default: "h-10 px-4 py-2",
    sm: "h-8 px-3 text-sm",
    lg: "h-12 px-6",
    icon: "h-8 w-8 rounded-full aspect-[1/1]",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Button.displayName = "Button";

export const PromptInputBox = React.forwardRef((props, ref) => {
  const {
    onSend = () => { },
    onFileUpload = null,
    isLoading = false,
    placeholder = "Paste form URL here...",
    className,
    acceptedFileTypes = ".pdf,.docx,.doc",
  } = props;
  const [input, setInput] = React.useState("");
  const [attachedFile, setAttachedFile] = React.useState(null);
  const uploadInputRef = React.useRef(null);
  const { isDark } = useTheme();

  const handleSubmit = () => {
    if (attachedFile && onFileUpload) {
      onFileUpload(attachedFile);
      setAttachedFile(null);
      setInput("");
    } else if (input.trim()) {
      onSend(input);
      setInput("");
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const validTypes = ['.pdf', '.docx', '.doc'];
      const fileExt = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

      if (validTypes.includes(fileExt)) {
        setAttachedFile(file);
        setInput(`📎 ${file.name}`);
      } else {
        alert('Please upload a PDF or Word document');
      }
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const removeAttachment = () => {
    setAttachedFile(null);
    setInput("");
  };

  const hasContent = input.trim() !== "" || attachedFile !== null;

  // Determine button tooltip
  const getTooltip = () => {
    if (isLoading) return "Analyzing...";
    if (attachedFile) return `Upload ${attachedFile.name.split('.').pop().toUpperCase()}`;
    if (input.trim()) return "Analyze form";
    return "Enter URL or attach file";
  };

  return (
    <PromptInput
      value={input}
      onValueChange={(val) => {
        // Don't allow editing when file is attached
        if (!attachedFile) {
          setInput(val);
        }
      }}
      isLoading={isLoading}
      onSubmit={handleSubmit}
      className={cn("w-full border-zinc-700 dark:border-zinc-300", className)}
      style={{ backgroundColor: isDark ? '#ffffff' : '#18181b' }}
      disabled={isLoading}
      ref={ref}
    >
      {/* File attachment preview */}
      {attachedFile && (
        <div className="flex items-center gap-2 px-3 py-2 mb-2 rounded-lg bg-zinc-800/50 dark:bg-zinc-100/50">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-lg">
              {attachedFile.name.endsWith('.pdf') ? '📄' : '📝'}
            </span>
            <span className={cn(
              "text-sm font-medium truncate",
              isDark ? "text-zinc-800" : "text-zinc-200"
            )}>
              {attachedFile.name}
            </span>
            <span className={cn(
              "text-xs",
              isDark ? "text-zinc-500" : "text-zinc-400"
            )}>
              ({(attachedFile.size / 1024).toFixed(1)} KB)
            </span>
          </div>
          <button
            onClick={removeAttachment}
            className="p-1 rounded-full hover:bg-zinc-700 dark:hover:bg-zinc-300 transition-colors"
          >
            <svg className={cn("w-4 h-4", isDark ? "text-zinc-600" : "text-zinc-400")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <PromptInputTextarea
        placeholder={attachedFile ? "File attached - click send to upload" : placeholder}
        className="text-base"
      />

      <PromptInputActions className="flex items-center justify-between gap-2 p-0 pt-2">
        <div className="flex items-center gap-1">
          <PromptInputAction tooltip="Attach PDF or Word document">
            <button
              onClick={() => uploadInputRef.current?.click()}
              className={cn(
                "flex h-8 w-8 cursor-pointer items-center justify-center rounded-full transition-colors",
                attachedFile
                  ? "bg-green-500/20 text-green-500"
                  : "text-zinc-400 dark:text-zinc-500 hover:bg-zinc-800 dark:hover:bg-zinc-200 hover:text-white dark:hover:text-zinc-900"
              )}
            >
              <Paperclip className="h-5 w-5 transition-colors" />
              <input
                ref={uploadInputRef}
                type="file"
                className="hidden"
                accept={acceptedFileTypes}
                onChange={handleFileChange}
              />
            </button>
          </PromptInputAction>
        </div>

        <PromptInputAction tooltip={getTooltip()}>
          <Button
            variant="default"
            size="icon"
            className={cn(
              "h-8 w-8 rounded-full transition-all duration-200",
              hasContent
                ? "bg-white hover:bg-zinc-200 text-zinc-900 dark:bg-zinc-900 dark:hover:bg-zinc-800 dark:text-white"
                : "bg-transparent hover:bg-zinc-800 dark:hover:bg-zinc-200 text-zinc-400 dark:text-zinc-400 hover:text-white dark:hover:text-zinc-600"
            )}
            onClick={handleSubmit}
            disabled={isLoading || !hasContent}
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        </PromptInputAction>
      </PromptInputActions>
    </PromptInput>
  );
});
PromptInputBox.displayName = "PromptInputBox";

