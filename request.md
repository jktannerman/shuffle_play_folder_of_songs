### Song player project specification

# Requirements
Please write a Python program that takes folders containing audio/video files and allows the user to select which to play via a GUI. On selection, the program should use VLC Media Player to play them. 
The order should either be 'straight' - the same order as the playlist - or 'shuffle' - a random order. 

# Memory
The program should remember which folders have been opened most recently and put those closest to the top/left.
Upon being closed and reopened, the program should remember the previous state of a given playlist - it should begin from the song that it left off. In 'shuffle' mode, the same order as before should be used unless the shuffle button is pressed again.

# Miscellaneous Details
The program should ignore non-audio/video files. 