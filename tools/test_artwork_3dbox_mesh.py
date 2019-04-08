#!/usr/bin/python3
#
# The 3D box mesh script uses the perspective projection to map the 3D model of the 3D box
# into a set of 2D polygons on the screen. These 2D polygons are then used by the
# 3D Box Texture Projection script to plot the textures into the final 3D Box image.
#
import sys
import math
import os
import pygame

class Point3D:
    def __init__(self, x = 0, y = 0, z = 0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def rotateX(self, angle):
        """ Rotates the point around the X axis by the given angle in degrees. """
        rad = angle * math.pi / 180
        cosa = math.cos(rad)
        sina = math.sin(rad)
        y = self.y * cosa - self.z * sina
        z = self.y * sina + self.z * cosa
        return Point3D(self.x, y, z)

    def rotateY(self, angle):
        """ Rotates the point around the Y axis by the given angle in degrees. """
        rad = angle * math.pi / 180
        cosa = math.cos(rad)
        sina = math.sin(rad)
        z = self.z * cosa - self.x * sina
        x = self.z * sina + self.x * cosa
        return Point3D(x, self.y, z)

    def rotateZ(self, angle):
        """ Rotates the point around the Z axis by the given angle in degrees. """
        rad = angle * math.pi / 180
        cosa = math.cos(rad)
        sina = math.sin(rad)
        x = self.x * cosa - self.y * sina
        y = self.x * sina + self.y * cosa
        return Point3D(x, y, self.z)

    def project(self, win_width, win_height, fov, viewer_distance):
        """ Transforms this 3D point to 2D using a perspective projection. """
        factor = fov / (viewer_distance - self.z)
        x = self.x * factor + win_width / 2
        y = -self.y * factor + win_height / 2
        return Point3D(x, y, self.z)

# --- 3D model of the box ---
spine_length = 300
box_width = 1000
box_heigth = 1500
front_offset = 40
front_height = 1350
name_height = 60
clearlogo_offset = 40
clearlogo_length = 500

vertices = [
    # Spine
    Point3D(0, 0, box_heigth),
    Point3D(spine_length, 0, box_heigth),
    Point3D(spine_length, 0, 0),
    Point3D(0, 0, 0),
    # Front
    Point3D(spine_length, 0, box_heigth),
    Point3D(spine_length, box_width, box_heigth),
    Point3D(spine_length, box_width, 0),
    Point3D(spine_length, 0, 0),
    # Poster vertices (plane x = 250)
    Point3D(spine_length, front_offset, front_offset + front_height),
    Point3D(spine_length, box_width-front_offset, front_offset + front_height),
    Point3D(spine_length, box_width-front_offset, front_offset),
    Point3D(spine_length, front_offset, front_offset),
    # Spine clearlogo vertices (plane y = 0)
    Point3D(clearlogo_offset, 0, clearlogo_offset + clearlogo_length),
    Point3D(spine_length - clearlogo_offset, 0, clearlogo_offset + clearlogo_length),
    Point3D(spine_length - clearlogo_offset, 0, clearlogo_offset),
    Point3D(clearlogo_offset, 0, clearlogo_offset),
    # Spine MAME clearlogo vertices
    Point3D(clearlogo_offset, 0, box_heigth - clearlogo_offset),
    Point3D(spine_length - clearlogo_offset, 0, box_heigth - clearlogo_offset),
    Point3D(spine_length - clearlogo_offset, 0, box_heigth - clearlogo_offset - clearlogo_length),
    Point3D(clearlogo_offset, 0, box_heigth - clearlogo_offset - clearlogo_length),
    # Machine name
    Point3D(spine_length, front_offset, box_heigth - front_offset),
    Point3D(spine_length, box_width-front_offset, box_heigth - front_offset),
    Point3D(spine_length, box_width-front_offset, box_heigth - front_offset - name_height),
    Point3D(spine_length, front_offset, box_heigth - front_offset - name_height),
]

vertices_axis = [
    Point3D(0, 0, 0),
    Point3D(1000, 0, 0),
    Point3D(0, 1000, 0),
    Point3D(0, 0, 1000),
]

faces = [
    # Spine
    (0, 1, 2, 3),
    # Frontbox
    (4, 5, 6, 7),
    # Flyer
    (8, 9, 10, 11),
    # Clearlogo
    (12, 13, 14, 15),
    # MAME logo
    (16, 17, 18, 19),
    # Machine name
    (20, 21, 22, 23),
]

face_colors = [
    (255, 0, 0),
    (0, 255, 0),
    (100, 100, 100),
    (150, 150, 100),
    (150, 100, 150),
    (150, 150, 150),
]

# Projection variables
angleX = -90
angleY = -50
angleZ = 0
fov = 1200
viewer_distance = 3000

# --- main ----------------------------------------------------------------------------------------
os.environ['SDL_VIDEO_CENTERED'] = '1'
pygame.init()
pygame.display.list_modes()
myfont = pygame.font.Font('../fonts/Inconsolata.otf', 22)

win_width = 500
win_height = 750
screen = pygame.display.set_mode((win_width, win_height))
pygame.display.set_caption('AEL/AML 3Dbox model')

# Center model around axis
c_vertices = []
for v in vertices:
    c_vertices.append(Point3D(v.x - spine_length/2, v.y - box_width/2, v.z - box_heigth/2))

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if   event.key == pygame.K_e: angleX -= 5
            elif event.key == pygame.K_r: angleX += 5
            elif event.key == pygame.K_d: angleY -= 5
            elif event.key == pygame.K_f: angleY += 5
            elif event.key == pygame.K_c: angleZ -= 5
            elif event.key == pygame.K_v: angleZ += 5
            elif event.key == pygame.K_q: fov -= 25
            elif event.key == pygame.K_w: fov += 25
            elif event.key == pygame.K_a: viewer_distance -= 100
            elif event.key == pygame.K_s: viewer_distance += 100

    screen.fill((0, 0, 0))

    # It will hold transformed vertices.
    t = []
    for v in c_vertices:
        # Rotate the point around X axis, then around Y axis, and finally around Z axis.
        r = v.rotateX(angleX).rotateY(angleY).rotateZ(angleZ)
        # Transform the point from 3D to 2D
        p = r.project(screen.get_width(), screen.get_height(), fov, viewer_distance)
        # Put the point in the list of transformed vertices
        t.append(p)

    # Draw the faces using the Painter's algorithm:
    # Distant faces are drawn before the closer ones.
    for face_index in range(len(faces)):
        f = faces[face_index]
        pointlist = [
            (t[f[0]].x, t[f[0]].y), (t[f[1]].x, t[f[1]].y),
            (t[f[1]].x, t[f[1]].y), (t[f[2]].x, t[f[2]].y),
            (t[f[2]].x, t[f[2]].y), (t[f[3]].x, t[f[3]].y),
            (t[f[3]].x, t[f[3]].y), (t[f[0]].x, t[f[0]].y),
        ]
        pygame.draw.polygon(screen, face_colors[face_index], pointlist)

    # --- Draw cartesian axis ---
    t = []
    for v in vertices_axis:
        r = v.rotateX(angleX).rotateY(angleY).rotateZ(angleZ)
        p = r.project(screen.get_width(), screen.get_height(), fov, viewer_distance)
        t.append(p)
    pygame.draw.line(screen, (255, 0, 0), (t[0].x, t[0].y), (t[1].x, t[1].y), 3)
    pygame.draw.line(screen, (0, 255, 0), (t[0].x, t[0].y), (t[2].x, t[2].y), 3)
    pygame.draw.line(screen, (0, 0, 255), (t[0].x, t[0].y), (t[3].x, t[3].y), 3)

    # --- Draw text ---
    text_surface = myfont.render('angle X {0}'.format(angleX), True, (255, 0, 255))
    screen.blit(text_surface, (10, 10))
    text_surface = myfont.render('angle Y {0}'.format(angleY), True, (255, 0, 255))
    screen.blit(text_surface, (10, 30))
    text_surface = myfont.render('angle Z {0}'.format(angleZ), True, (255, 0, 255))
    screen.blit(text_surface, (10, 50))
    text_surface = myfont.render('FOV {0}'.format(fov), True, (255, 0, 255))
    screen.blit(text_surface, (10, 70))
    text_surface = myfont.render('distance {0}'.format(viewer_distance), True, (255, 0, 255))
    screen.blit(text_surface, (10, 90))

    # --- Refresh screen ---
    pygame.display.flip()
