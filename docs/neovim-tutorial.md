# Neovim tutorial: learn it by working in LocalLibrary

Each step is a small task in this repo. Do the steps in order; every one builds on the last.
This tutorial targets the LazyVim setup in the dotfiles repo (`dotfiles/dot_config/nvim`, managed by chezmoi). The leader key is `<Space>`; LazyVim shows a which-key popup after you press it, so you can discover mappings as you go.
Commands are typed in **Normal mode** unless they start with `:`. Press `<Esc>` to get back to Normal mode at any time.

## 0. Setup

1. Apply your dotfiles (`chezmoi apply`) so `~/.config/nvim` is in place, and install ripgrep and fd (`brew install ripgrep fd`) for the pickers.
2. From the repo root, run `nvim`. The first launch installs plugins via lazy.nvim; wait for it to finish.
3. The dashboard opens (the `ui.dashboard` extra). Press `<Space>l` to see the Lazy plugin manager, `<Space>cm` for Mason.
4. Quit with `:q`, `<Space>qq` (quit all), or `:qa!` to discard everything.

## 1. Move around and open files

netrw is disabled in your config; you use Neo-tree and the picker instead.

1. Press `<Space>e` to toggle the Neo-tree file explorer. Move with `j`/`k`, open folders and files with `<Enter>`, and press `?` inside the tree for its help. `<Space>e` again closes it.
2. Fuzzy-find a file with `<Space><Space>` (or `<Space>ff`). Type `views` and press `<Enter>` to open `catalog/views.py`.
3. Reopen recent files with `<Space>fr`. List open buffers with `<Space>,`.
4. Jump between the last two files with `<Ctrl-^>`, or cycle buffers with `<Shift-h>` / `<Shift-l>`.
5. `:e catalog/models.py` still works when you know the path.

## 2. Modes and basic motions

Open `catalog/views.py` and practice on `index()`:

| Keys | What it does |
| --- | --- |
| `h j k l` | left, down, up, right |
| `w` / `b` | next / previous word |
| `0` / `$` | start / end of line |
| `gg` / `G` | top / bottom of file |
| `42G` or `:42` | go to line 42 |
| `{` / `}` | previous / next blank line (paragraph) |
| `<Ctrl-d>` / `<Ctrl-u>` | half page down / up |

Exercise: go to `def index`, then use `}` to hop to the end of the function, then `gg` to go back.

## 3. Search

1. Press `/num_books<Enter>` to find the first match. `n` goes to the next, `N` to the previous.
2. Press `*` on any word to search for the word under the cursor.
3. Press `<Esc>` (LazyVim clears highlighting) or `:noh<Enter>` to clear highlighting.

Exercise: find every use of `Author` in `views.py`.

## 4. Edit text

1. Move onto `num_authors` and press `i` to enter Insert mode. Type, then `<Esc>`.
2. Learn the operator + motion pattern:
   - `dw` deletes a word, `dd` deletes a line, `D` deletes to end of line.
   - `cw` changes a word, `cc` changes a line.
   - `yy` yanks (copies) a line, `p` pastes below, `P` above.
   - `u` undo, `<Ctrl-r>` redo, `.` repeats the last change.
3. Use counts: `3dd` deletes three lines, `d2w` deletes two words.
4. Text objects: with the cursor inside `'num_books'`, `ci'` changes the text inside the quotes. Try `da(` / `ci"` too.

Exercise: in `catalog/urls.py`, change the `'authors/'` path to `'writers/'` using `ci'`, then undo with `u`.

## 5. Save, quit, and visual mode

1. `:w` saves, `:q` quits, `:wq` (or `ZZ`) does both.
2. Press `V` to select whole lines, move with `j`/`k`, then `d` to cut or `y` to copy.
3. `<Ctrl-v>` selects a block. Select the first column of `INSTALLED_APPS` entries in `locallibrary/settings.py` and press `I#<Esc>` to comment them all out. Undo with `u`.

## 6. Find and replace

1. In `catalog/views.py`, run `:%s/BookInstance/Copy/gc`. `%` is the whole file, `g` is every match on a line, `c` asks for confirmation (`y`/`n`/`a`/`q`).
2. Undo it all with `u`. Nothing is saved until you `:w`.
3. Replace only inside a selection: select lines with `V`, then type `:` and `s/old/new/g`.

## 7. Work across files

1. Grep the whole project with `<Space>/` (live grep through ripgrep). Type `search_ids`, move through results, `<Enter>` opens one. `<Space>sw` greps the word under the cursor.
2. Fuzzy-find a file by name with `<Space><Space>`.
3. With the cursor on `SearchListView` in `catalog/views.py`, press `gd` to go to its definition and `gr` to list references (needs the language server from step 11).
4. Open the symbol outline (the `editor.outline` extra) with `<Space>cs` to jump between `index`, `SearchListView`, `BookListView`, and so on. The breadcrumb at the top comes from the navic extra.

Exercise: find every place `rebuild_index` is called across `catalog/`.

## 8. Buffers, windows, tabs

- Every open file is a **buffer**. `<Space>,` lists them, `<Shift-h>`/`<Shift-l>` cycle, `<Space>bd` closes the current one.
- Split the view: `<Space>|` (side by side) or `<Space>-` (stacked). Move between windows with `<Ctrl-h/j/k/l>`. Close one with `<Space>wd`.
- Try it: open `catalog/views.py` and `catalog/templates/catalog/book_list.html` side by side to see a view and its template together.

## 9. Marks, jumps, and macros

1. `ma` sets mark `a`. Later `'a` jumps back to it. Set a mark in `views.py` and another in `models.py`, then jump between them.
2. `<Ctrl-o>` / `<Ctrl-i>` walk back and forward through your jump history.
3. Record a macro: `qa` start recording into register `a`, do some edits, `q` to stop. Replay with `@a`, or `10@a` to repeat.
   - Exercise: in `catalog/urls.py`, record a macro that appends a comment `# TODO` to one `path(...)` line and moves down; replay it for the others.

## 10. Run project tasks from Neovim

Run commands without leaving the editor with `:!`:

- `:!uv run python manage.py test` runs the test suite.
- `:!uv run ruff check %` lints the current file (`%` is the current filename).
- `:!uv run basedpyright %` type-checks it.
- `<Ctrl-/>` toggles a floating terminal (LazyVim's Snacks terminal); `<Ctrl-\><Ctrl-n>` returns to Normal mode inside it.

## 11. Your config and language servers

Your Neovim config is a LazyVim setup:

- `~/.config/nvim/init.lua` bootstraps lazy.nvim and imports LazyVim plus your own specs.
- `lua/plugins/ide.lua` enables the `neo-tree`, `navic`, `outline` and `dashboard` extras, plus the `python`, `ruby`, `go` and `sql` language extras.
- `lua/config/options.lua` sets `vim.g.lazyvim_python_lsp = "basedpyright"`, matching this repo's `pyproject.toml`.
- It comes from `dotfiles/dot_config/nvim`, so edit it there (or with `chezmoi edit ~/.config/nvim/lua/plugins/ide.lua`) and run `chezmoi apply`, otherwise your changes get overwritten.

LazyVim already gives you relative line numbers, `ignorecase`/`smartcase`, and `<Ctrl-s>` to save, so you don't need to set those yourself. Put personal keymaps in `lua/config/keymaps.lua` (it doesn't exist in your dotfiles yet).

### Python tooling for this repo

On first launch Mason installs `basedpyright` and `ruff`. Open `catalog/models.py`, then check `:LspInfo` and `:Mason`. Try these on `Book`:

- `K` hover, `gd` definition, `gr` references
- `<Space>cr` rename, `<Space>ca` code action
- `<Space>cf` format (ruff), `<Space>cd` line diagnostics

The other extras work the same way: `gopls` for Go, `ruby_lsp` and `rubocop` for Ruby. SQL has no language server; it gets `sqlfluff` formatting and linting, and the database UI on `<Space>D`.

## 12. Final challenge

Using only Neovim, add a `/genres/` page's worth of plumbing as a dry run (don't commit it):

1. Open `catalog/urls.py` and `catalog/views.py` in a vertical split (`<Space>|`).
2. Yank the `books` URL line (`yy`), paste it (`p`), and change it into a `genres` entry with `ci'`.
3. Yank `BookListView` (`V` the class, `y`, `p`) and rename the copy with `:s/Book/Genre/g` on the pasted lines.
4. Run `:!uv run ruff check %` and `:!uv run python manage.py check`.
5. Revert with `:e!` in each buffer, or `git restore .` in the floating terminal (`<Ctrl-/>`).

## Cheat sheet

`i`/`a`/`o` insert, `<Esc>` normal, `v`/`V`/`<Ctrl-v>` visual, `d`/`c`/`y` operators, `.` repeat, `u` undo, `/` search, `:%s` replace, `<Space>/` project search, `<Space>e` explorer, `<Space><Space>` find file, `<Space>|` split, `qa`/`@a` macros, `:help <topic>` for anything else, `<Space>sk` to search keymaps. Your config disables the `tutor` plugin, so `:Tutor` is unavailable unless you remove it from `disabled_plugins` in `init.lua`.
