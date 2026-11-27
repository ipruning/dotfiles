" Vim skips defaults.vim once ~/.vimrc exists; keep its modern defaults.
unlet! skip_defaults_vim
source $VIMRUNTIME/defaults.vim

nnoremap <C-d> <C-d>zz
nnoremap <C-u> <C-u>zz
nnoremap n nzz
nnoremap N Nzz
