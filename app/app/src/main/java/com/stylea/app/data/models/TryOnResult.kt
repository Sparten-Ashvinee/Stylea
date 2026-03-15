package com.stylea.app.data.models

import android.graphics.Bitmap

/**
 * Holds the result of a virtual try-on request.
 *
 * @param tryOnBitmap      Composited image: person wearing the segmented outfit.
 * @param segmentedBitmap  Segmented clothing on a white background.
 */
data class TryOnResult(
    val tryOnBitmap: Bitmap,
    val segmentedBitmap: Bitmap,
)
