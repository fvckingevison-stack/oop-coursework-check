import multiprocessing

from app import WardrobeApp

if __name__ == "__main__":
    multiprocessing.freeze_support()
    WardrobeApp().mainloop()