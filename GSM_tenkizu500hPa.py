#!/usr/bin/env python
# coding: utf-8

# In[1]:


import math
import pygrib
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import matplotlib.path as mpath
import cartopy.crs as ccrs
import datetime
import sys
#
import metpy.calc as mpcalc
from metpy.units import units
from scipy.ndimage.filters import maximum_filter, minimum_filter
#
import argparse


# In[2]:


## 緯度経度で指定したポイントの図上の座標などを取得する関数 transform_lonlat_to_figure() 
# 図法の座標 => pixel座標 => 図の座標　と3回の変換を行う
#  　pixel座標: plt.figureで指定した大きさxDPIに合わせ、左下を原点とするpixelで測った座標   
#  　図の座標: axesで指定した範囲を(0,1)x(0,1)とする座標
# 3つの座標を出力する
#    図の座標, Pixel座標, 図法の座標
def transform_lonlat_to_figure(lonlat, ax, proj):
    # lonlat:経度と緯度  (lon, lat) 
    # ax: Axes図の座標系    ex. fig.add_subplot()の戻り値
    # proj: axで指定した図法 
    #
    # 例 緯度経度をpointで与え、ステレオ図法る場合
    #    point = (140.0,35.0)
    #    proj= ccrs.Stereographic(central_latitude=60, central_longitude=140) 
    #    fig = plt.figure(figsize=(20,16))
    #    ax = fig.add_subplot(1, 1, 1, projection=proj)
    #    ax.set_extent([108, 156, 17, 55], ccrs.PlateCarree())
    #
    ## 図法の変換
    # 参照  https://scitools.org.uk/cartopy/docs/v0.14/crs/index.html                    
    point_proj = proj.transform_point(*lonlat, ccrs.PlateCarree())
    #
    # pixel座標へ変換
    # 参照　https://matplotlib.org/stable/tutorials/advanced/transforms_tutorial.html
    point_pix = ax.transData.transform(point_proj)
    #
    # 図の座標へ変換                                                           
    point_fig = ax.transAxes.inverted().transform(point_pix)
    return point_fig, point_pix, point_proj


# In[3]:


## 極大/極小ピーク検出関数                                                             
def detect_peaks(image, filter_size=3, dist_cut=5.0, flag=0):
    # filter_size: この値xこの値 の範囲内の最大値のピークを検出                        
    # dist_cut: この距離内のピークは1つにまとめる                                      
    # flag:  0:maximum検出  0以外:minimum検出                                          
    if flag==0:
      local_max = maximum_filter(image,
            footprint=np.ones((filter_size, filter_size)), mode='constant')
      detected_peaks = np.ma.array(image, mask=~(image == local_max))
    else:
      local_min = minimum_filter(image,
            footprint=np.ones((filter_size, filter_size)), mode='constant')
      detected_peaks = np.ma.array(image, mask=~(image == local_min))
    peaks_index = np.where((detected_peaks.mask != True))
    # peak間の距離行例を求める                                                         
    (x,y) = peaks_index
    size=y.size
    dist=np.full((y.size, y.size), -1.0)
    for i in range(size):
      for j in range(size):
        if i == j:
          dist[i][j]=0.0
        elif i>j:
          d = math.sqrt(((y[i] - y[j])*(y[i] - y[j]))
                        +((x[i] - x[j])*(x[i] - x[j])))
          dist[i][j]= d
          dist[j][i]= d
    # 距離がdist_cut内のpeaksの距離の和と、そのピーク番号を取得する 
    Kinrin=[]
    dSum=[]
    for i in range(size):
      tmpA=[]
      distSum=0.0
      for j in range(size):
        if dist[i][j] < dist_cut and dist[i][j] > 0.0:
          tmpA.append(j)
          distSum=distSum+dist[i][j]
      dSum.append(distSum)
      Kinrin.append(tmpA)
    # Peakから外すPeak番号を求める.  peak間の距離和が最も小さいものを残す              
    cutPoint=[]
    for i in range(size):
      val = dSum[i]
      val_i=image[x[i]][y[i]]
      for k in Kinrin[i]:
        val_k=image[x[k]][y[k]]
        if flag==0 and val_i < val_k:
            cutPoint.append(i)
            break
        if flag!=0 and val_i > val_k:
            cutPoint.append(i)
            break
        if val > dSum[k]:
            cutPoint.append(i)
            break
        if val == dSum[k] and i > k:
            cutPoint.append(i)
            break
    # 戻り値用に外すpeak番号を配列から削除                                             
    newx=[]
    newy=[]
    for i in range(size):
      if (i in cutPoint):
        continue
      newx.append(x[i])
      newy.append(y[i])
    peaks_index=(np.array(newx),np.array(newy))
    return peaks_index


# In[4]:


# GSMの読み込む初期値の年月日時をUTCで与えます。
i_year =2021
i_month = 8
i_day = 23
i_hourZ = 0
#
# 予想時間を与える。この値は注意が必要です。下3桁目が日数、下２桁で時間で与えます。
#  初期値なら0、18時間後なら18、24時間後なら100、36時間後なら112となります。
i_ft = 0
#
# 読み込む気圧面の気圧を与えます。ここでは500hPaと指定します。
tagHp = 500
#
# データの格納先フォルダー名
##!!! GRIB2データの保存先をFolderを指定すること !!!
data_fld="./data/gsm/"
####################################################
#
# 読み込むGRIB2形式GSMのファイル名
gsm_fn_t="Z__C_RJTD_{0:4d}{1:02d}{2:02d}{3:02d}0000_GSM_GPV_Rgl_FD{4:04d}_grib2.bin"
gr_fn= gsm_fn_t.format(i_year,i_month,i_day,i_hourZ,i_ft)
#
# データOpen
grbs = pygrib.open(data_fld + gr_fn)
#
# データ取得                                                                                                                       
grbHt = grbs(shortName="gh",typeOfLevel='isobaricInhPa',level=tagHp)[0]
grbWu = grbs(shortName="u",typeOfLevel='isobaricInhPa',level=tagHp)[0]
grbWv = grbs(shortName="v",typeOfLevel='isobaricInhPa',level=tagHp)[0]
#
# データClose
grbs.close()
#
print(gr_fn)


# In[5]:


## GPVの切り出し領域の指定：(lonW,latS)-(lonE,latN)の矩形                                                                                                      
latS=-20
latN=80
lonW=70
lonE=190
## データ切り出し                                                                                                                   
valHt, latHt, lonHt = grbHt.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)
valWu, latWu, lonWu = grbWu.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)
valWv, latWv, lonWv = grbWv.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)


# In[6]:


## 渦度などの算出のためにxarrayデータセットを作成                                                                                   
ds = xr.Dataset(
   {
       "Geopotential_height": (["lat", "lon"], valHt),                                                                        
       "u_wind": (["lat", "lon"], valWu),
       "v_wind": (["lat", "lon"], valWv),
   },
   coords={
       "level": [tagHp],
       "lat": latHt[:,0],
       "lon": lonHt[0,:],
       "time": [grbHt.validDate],
   },
)
# 単位も入力する
ds['Geopotential_height'].attrs['units'] = 'm'
ds['u_wind'].attrs['units']='m/s'
ds['v_wind'].attrs['units']='m/s'
ds['level'].attrs['units'] = 'hPa'
ds['lat'].attrs['units'] = 'degrees_north'
ds['lon'].attrs['units'] = 'degrees_east'
#print(ds)


# In[7]:


## 算出                                                                                                                             
# 相対渦度                                                                                                                          
ds['vorticity'] = mpcalc.vorticity(ds['u_wind'],ds['v_wind'])
#print(ds)


# In[8]:


## 表示用の指定
# 図法指定　気象庁の数値予報資料と同じ図法に設定                                                                                
proj = ccrs.Stereographic(central_latitude=60, central_longitude=140)
latlon_proj = ccrs.PlateCarree() # 緯度経度の処理用に正距円筒図法も使う  
#
# 地図の描画範囲指定
areaAry = [108, 156, 17, 55]  # 極東
#areaAry = [115, 151, 20, 50]  # 日本付近
#
# 等値線の間隔を指定
levels_ht =np.arange(4800, 6000,  60)  # 高度を60m間隔で実線                       
levels_ht2=np.arange(4800, 6000, 300)  # 高度を300m間隔で太線
levels_vr =np.arange(-0.0002, 0.0002, 0.00004)  # 渦度4e-5毎に等値線
#
# 渦度のハッチの指定
levels_h_vr = [0.0, 0.00008, 1.0]    # 0.0以上で 灰色(0.9), 8e-5以上で赤
colors_h_vr = ['0.9','red']
alpha_h_vr = 0.3                     # 透過率を指定
#
# 緯度・経度線の指定
dlon,dlat=10,10   # 10度ごとに
#
## タイトル文字列用
# 予想時間を得る
ft_hours=int(i_ft/100) * 24 + int(i_ft%100)
# 初期時刻の文字列
dt_i = grbHt.analDate
dt_str = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
dt_str2 = dt_i.strftime("%Y%m%d%H")


# In[16]:


## 図のSIZE指定inch                                                                        
fig = plt.figure(figsize=(10,8))
## 余白設定                                                                                
plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)                  
## 作図                                                                                    
ax = fig.add_subplot(1, 1, 1, projection=proj)
ax.set_extent(areaAry, latlon_proj)

# 500hPa 相対渦度のハッチ 0.0以上:着色  0.8*10**-4以上:赤                                  
cn_relv_hatch2 = ax.contourf(ds['lon'], ds['lat'], ds['vorticity'],
        levels_h_vr, colors=colors_h_vr,
        alpha=alpha_h_vr, transform=latlon_proj)
# 5000hPa 相対渦度 実線 0.00004毎 負は破線                                                 
cn_relv = ax.contour(ds['lon'], ds['lat'], ds['vorticity'],
        levels_vr, colors='black', linewidths=1.0, transform=latlon_proj)
# 500hPa  等高度線 実線 step1:60m毎                                                                                                          
cn_hgt = ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                    colors='black',
                    linewidths=1.2, levels=levels_ht, transform=latlon_proj )
ax.clabel(cn_hgt, levels_ht, fontsize=15, inline=True, inline_spacing=5,
          fmt='%i', rightside_up=True)
# 500hPa 等高度線 太線 step1:300m毎                                                        
cn_hgt2= ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                    colors='black',
                    linewidths=1.5, levels=levels_ht2, transform=latlon_proj)
ax.clabel(cn_hgt2, fontsize=15, inline=True, inline_spacing=0,
          fmt='%i', rightside_up=True)
# 500hPa 5820gpm高度線 茶色                                                         
cn5820 = ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                    colors='brown',linestyles='dashdot',
                    linewidths=1.2, levels=[5820], transform=latlon_proj )
# 500hPa 5400gpm高度線 青                                                             
cn5400 = ax.contour(ds['lon'], ds['lat'], ds['Geopotential_height'],
                    colors='blue',linestyles='dashdot',
                    linewidths=1.2, levels=[5400], transform=latlon_proj )
## + stamp                                                                                                 
maxid = detect_peaks(ds['vorticity'].values, filter_size=3, dist_cut=4.0)
for i in range(len(maxid[0])):
  wlon = ds['lon'][maxid[1][i]]
  wlat = ds['lat'][maxid[0][i]]
  # 図の範囲内に座標があるか確認                                                                           
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.0 and fig_z[0] < 1.0  and fig_z[1] > 0.0 and fig_z[1] < 1.0):
    val = ds['vorticity'].values[maxid[0][i]][maxid[1][i]]
    ival = int(val * 1000000.0)
    if ival > 30:
      ax.plot(wlon, wlat, marker='+' , markersize=7, color="red", transform=latlon_proj)
      if ival > 50:
        ax.text(fig_z[0], fig_z[1]-0.01, str(ival), size=14, color="black", transform=ax.transAxes,
                verticalalignment="top", horizontalalignment="center")
## - stamp ないので他にする                                                
minid = detect_peaks(ds['vorticity'].values, filter_size=3, dist_cut=4.0,flag=1)
for i in range(len(minid[0])):
  wlon = ds['lon'][minid[1][i]]
  wlat = ds['lat'][minid[0][i]]
  # 図の範囲内に座標があるか確認                                                                           
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.0 and fig_z[0] < 1.0  and fig_z[1] > 0.0 and fig_z[1] < 1.0):
    val = ds['vorticity'].values[minid[0][i]][minid[1][i]]
    ival = int(val * -1000000.0)
    if ival > 30:
      ax.plot(wlon, wlat, marker='_' , markersize=8, color="blue",transform=latlon_proj)
      if ival > 50:
        ax.text(fig_z[0], fig_z[1]-0.01, str(ival), size=12, color="blue", transform=ax.transAxes,
                verticalalignment="top", horizontalalignment="center")
## H stamp                                                                                                 
maxid = detect_peaks(ds['Geopotential_height'].values, filter_size=10, dist_cut=8.0)
for i in range(len(maxid[0])):
  wlon = ds['lon'][maxid[1][i]]
  wlat = ds['lat'][maxid[0][i]]
  # 図の範囲内に座標があるか確認                                                                           
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.0 and fig_z[0] < 1.0  and fig_z[1] > 0.0 and fig_z[1] < 1.0):
    ax.text(wlon, wlat, 'H', size=24, color="blue",
            ha='center', va='center', transform=latlon_proj)
## L stamp                                                                                                 
minid = detect_peaks(ds['Geopotential_height'].values, filter_size=10, dist_cut=8.0,flag=1)
for i in range(len(minid[0])):
  wlon = ds['lon'][minid[1][i]]
  wlat = ds['lat'][minid[0][i]]
  # 図の範囲内に座標があるか確認                                                                           
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.0 and fig_z[0] < 1.0  and fig_z[1] > 0.0 and fig_z[1] < 1.0):
    ax.text(wlon, wlat, 'L', size=24, color="red",
            ha='center', va='center', transform=latlon_proj)
#
#
## 海岸線                                                                                                                               
ax.coastlines(resolution='50m',)
## グリッド                                                                   
xticks=np.arange(0,360.1,dlon)
yticks=np.arange(-90,90.1,dlat)
gl = ax.gridlines(crs=ccrs.PlateCarree()
         , draw_labels=False
         , linewidth=1, alpha=0.8)
gl.xlocator = mticker.FixedLocator(xticks)
gl.ylocator = mticker.FixedLocator(yticks)
#                                                                                          
## Title                                                                        
fig.text(0.5,0.01,
         "GSM FT{0:d} IT:".format(ft_hours)+dt_str+" 500hPa Height(m),VORT" ,
         ha='center',va='bottom', size=18)
## 出力                                                                                    
out_fn="gsm_{0}UTC_FT{1:03d}_50.png".format(dt_str2,ft_hours)
plt.savefig(out_fn)
print("output:{}".format(out_fn))
# plt.show()  # 画面表示する場合はコメントアウトを外す
plt.close()


# In[ ]:




