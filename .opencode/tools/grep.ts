import { tool } from "@opencode-ai/plugin"

export default tool({
  description: `Fast content search tool with safety limits (60s timeout, 256KB output). Searches file contents using regular expressions. Supports full regex syntax (eg. "log.*Error", "function\\s+\\w+", etc.). Filter files by pattern with the include parameter (eg. "*.js", "*.{ts,tsx}"). Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts per file.`,
  args: {
    pattern: tool.schema.string().describe("The regular expression pattern to search for"),
    path: tool.schema.string().optional().describe("The directory to search in (defaults to current working directory)"),
    include: tool.schema.string().optional().describe("Filter files by pattern (eg. \"*.js\", \"*.{ts,tsx}\")"),
    output_mode: tool.schema.enum(["content", "files_with_matches", "count"]).optional().default("files_with_matches").describe("Output mode: content shows matching lines, files_with_matches shows only file paths, count shows match counts"),
    ignoreCase: tool.schema.boolean().optional().default(false).describe("Case-insensitive search"),
    context: tool.schema.number().optional().describe("Number of context lines to show before and after matches"),
    head_limit: tool.schema.number().optional().describe("Maximum number of results to return"),
  },
  async execute(args, context) {
    const searchPath = args.path || context.directory || "."
    const pattern = args.pattern
    const include = args.include
    const outputMode = args.output_mode || "files_with_matches"
    const ignoreCase = args.ignoreCase || false
    const contextLines = args.context || 0
    const headLimit = args.head_limit || 0
    
    // Build rg command arguments
    const rgArgs: string[] = ["rg"]
    
    // Output mode
    if (outputMode === "files_with_matches") {
      rgArgs.push("--files-with-matches")
    } else if (outputMode === "count") {
      rgArgs.push("--count")
    } else {
      rgArgs.push("--line-number")
    }
    
    // Case insensitive
    if (ignoreCase) {
      rgArgs.push("--ignore-case")
    }
    
    // Context lines
    if (contextLines > 0) {
      rgArgs.push("--context", String(contextLines))
    }
    
    // File include pattern
    if (include) {
      rgArgs.push("--glob", include)
    }
    
    // Use --no-heading for cleaner output
    rgArgs.push("--no-heading")
    
    // Disable colors for clean output
    rgArgs.push("--color", "never")
    
    // Add regex pattern
    rgArgs.push(pattern)
    
    // Add path
    rgArgs.push(searchPath)
    
    try {
      // Debug: log the command
      const debugCmd = `rg ${rgArgs.slice(1).map(a => a.includes(" ") || a.includes("|") ? `"${a}"` : a).join(" ")}`
      
      // Use Bun.spawn for proper argument handling
      const proc = Bun.spawn(rgArgs, {
        cwd: context.worktree || context.directory || undefined,
        timeout: 60000,
      })
      
      const stdout = await new Response(proc.stdout).text()
      const stderr = await new Response(proc.stderr).text()
      const exitCode = await proc.exited
      
      // Debug output
      if (stdout.trim() === "") {
        return `No matches found for pattern: ${pattern}\n[Debug] Command: ${debugCmd}\n[Debug] Exit code: ${exitCode}\n[Debug] Stderr: ${stderr.trim() || "(empty)"}`
      }
      
      let output = stdout
      
      // Limit output size (256KB)
      const maxSize = 256 * 1024
      if (output.length > maxSize) {
        output = output.substring(0, maxSize) + "\n... (output truncated due to size limit)"
      }
      
      // Apply head limit
      if (headLimit > 0) {
        const lines = output.split("\n")
        if (lines.length > headLimit) {
          output = lines.slice(0, headLimit).join("\n") + "\n... (limited to " + headLimit + " results)"
        }
      }
      
      if (output.trim() === "") {
        return `No matches found for pattern: ${pattern}`
      }
      
      return `=== CUSTOM GREP TOOL ===\nFound ${output.split("\n").filter(l => l.trim()).length} match(es)\n` + output
    } catch (error: any) {
      // Check if it's a timeout
      if (error.name === "TimeoutError" || error.message?.includes("timeout")) {
        return `Search timed out after 60 seconds. Try narrowing your search with a more specific pattern or include filter.`
      }
      
      return `Error searching: ${error.message || error}`
    }
  },
})