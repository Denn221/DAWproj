import tkinter as tk

def create_controls(app):
    control_frame = tk.Frame(app.root, bg="lightgrey", height=60)
    control_frame.pack(fill=tk.X)

    #play Button
    app.play_button = tk.Button(control_frame, text="Play", command=app.play_audio, width=10)
    app.play_button.pack(side=tk.LEFT, padx=10)

    #pause Button
    app.pause_button = tk.Button(control_frame, text="Pause", command=app.pause_audio, width=10)
    app.pause_button.pack(side=tk.LEFT, padx=10)

    #BPM Slider
    bpm_label = tk.Label(control_frame, text="BPM:", bg="lightgrey", font=("Arial", 12))
    bpm_label.pack(side=tk.LEFT, padx=10)

    bpm_slider = tk.Scale(
        control_frame, from_=60, to=240, orient=tk.HORIZONTAL, bg="lightgrey", command=app.update_bpm
    )
    bpm_slider.set(app.bpm)
    bpm_slider.pack(side=tk.LEFT, padx=10)

    #BPM Display
    app.bpm_display = tk.Label(control_frame, text=f"{app.bpm} BPM", bg="lightgrey", font=("Arial", 12))
    app.bpm_display.pack(side=tk.LEFT, padx=10)

    #volume Slider
    volume_label = tk.Label(control_frame, text="Volume:", bg="lightgrey", font=("Arial", 12))
    volume_label.pack(side=tk.LEFT, padx=10)

    app.volume_slider = tk.Scale(
        control_frame, from_=-50, to=5, orient=tk.HORIZONTAL, bg="lightgrey", command=app.update_volume
    )
    app.volume_slider.set(-20)  
    app.volume_slider.pack(side=tk.LEFT, padx=10)

    #division Selector
    division_label = tk.Label(control_frame, text="Grid Division:", bg="lightgrey", font=("Arial", 12))
    division_label.pack(side=tk.LEFT, padx=10)

    app.division_var = tk.StringVar()
    app.division_var.set("1/1") 
    divisions = ["1/1", "1/2", "1/3", "1/4"]
    app.division_map = {"1/1": 1, "1/2": 2, "1/3": 3, "1/4": 4}
    division_menu = tk.OptionMenu(control_frame, app.division_var, *divisions, command=app.update_division)
    division_menu.config(width=5)
    division_menu.pack(side=tk.LEFT, padx=10)

    #import Button
    import_button = tk.Button(control_frame, text="Import Audio", command=app.import_audio)
    import_button.pack(side=tk.LEFT, padx=10)

    #export Button
    export_button = tk.Button(control_frame, text="Export Arrangement", command=app.export_audio)
    export_button.pack(side=tk.LEFT, padx=10)

def create_timeline(app):
    timeline_frame = tk.Frame(app.root, bg="white")
    timeline_frame.pack(fill=tk.BOTH, expand=True)

    #track labels
    main_frame = tk.Frame(timeline_frame)
    main_frame.pack(fill=tk.BOTH, expand=True)

    tracks_frame = tk.Frame(main_frame, width=100, bg="lightgrey")
    tracks_frame.pack(side=tk.LEFT, fill=tk.Y)

    for track_num in range(1, 6):
        track_label = tk.Label(tracks_frame, text=f"Track {track_num}", bg="lightgrey", width=12, anchor="w")
        track_label.place(x=0, y=(track_num - 1) * 100, height=100)

    canvas_frame = tk.Frame(main_frame)
    canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

    #ruler Canvas
    app.ruler_canvas = tk.Canvas(canvas_frame, bg="lightgrey", height=30)  # Increased height
    app.ruler_canvas.pack(fill=tk.X, side=tk.TOP)

    #timeline Canvas
    app.timeline_canvas = tk.Canvas(canvas_frame, bg="white")
    app.timeline_canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    #vertical Scrollbar
    v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=app.timeline_canvas.yview)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    app.timeline_canvas.config(yscrollcommand=v_scrollbar.set)

    #horizontal Scrollbar
    h_scrollbar = tk.Scrollbar(timeline_frame, orient=tk.HORIZONTAL, command=app.xview)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    app.timeline_canvas.config(xscrollcommand=h_scrollbar.set)
    app.ruler_canvas.config(xscrollcommand=h_scrollbar.set)

    total_seconds = 600  
    total_width = total_seconds * app.pixels_per_second
    app.timeline_canvas.config(scrollregion=(0, 0, total_width, 500))
    app.ruler_canvas.config(scrollregion=(0, 0, total_width, 30))

    #playhead
    app.playhead = app.timeline_canvas.create_line(0, 0, 0, 500, fill="red", width=2)
    app.ruler_playhead = app.ruler_canvas.create_line(0, 0, 0, 30, fill="red", width=2)

    #grid
    app.draw_ruler()
    app.draw_grid()

    app.ruler_canvas.bind("<Button-1>", app.move_playhead_click)
    app.ruler_canvas.bind("<B1-Motion>", app.move_playhead_drag)

    #drag
    app.timeline_canvas.bind("<Button-1>", app.select_clip)
    app.timeline_canvas.bind("<B1-Motion>", app.move_clip)
    app.timeline_canvas.bind("<ButtonRelease-1>", app.snap_clip)

    app.root.bind("<BackSpace>", app.delete_selected_clip)
