package com.stylea.app.data.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Low-level HTTP client that talks to the Stylea Python backend.
 *
 * All calls are **synchronous** – callers are expected to dispatch on a
 * background coroutine / thread (e.g. `Dispatchers.IO`).
 */
class StyleaApiClient(private val baseUrl: String) {

    private val httpClient: OkHttpClient by lazy {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .addInterceptor(logging)
            .build()
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Health check. Returns true when the server is reachable.
     */
    fun isHealthy(): Boolean = try {
        val request = Request.Builder().url("$baseUrl/health").get().build()
        httpClient.newCall(request).execute().use { it.isSuccessful }
    } catch (_: Exception) {
        false
    }

    /**
     * Segment the clothing from a fashion image.
     *
     * @param fashionImageFile  JPEG / PNG file with the fashion photo.
     * @return Raw JPEG bytes of the segmented clothing on a white background.
     * @throws ApiException on non-2xx HTTP status or network failure.
     */
    fun segment(fashionImageFile: File): ByteArray {
        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "fashion_image",
                fashionImageFile.name,
                fashionImageFile.asRequestBody("image/jpeg".toMediaType()),
            )
            .build()

        val request = Request.Builder()
            .url("$baseUrl/segment")
            .post(requestBody)
            .build()

        return httpClient.newCall(request).execute().use { response ->
            response.requireSuccess("segment")
        }
    }

    /**
     * Virtual try-on: overlay clothing from [fashionImageFile] onto [personImageFile].
     *
     * @param personImageFile   Photo of the person.
     * @param fashionImageFile  Fashion / clothing photo.
     * @param blendAlpha        Clothing opacity 0–1 (default 0.92).
     * @return Raw JPEG bytes of the composited try-on image.
     * @throws ApiException on non-2xx HTTP status or network failure.
     */
    fun tryOn(
        personImageFile: File,
        fashionImageFile: File,
        blendAlpha: Float = 0.92f,
    ): ByteArray {
        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "person_image",
                personImageFile.name,
                personImageFile.asRequestBody("image/jpeg".toMediaType()),
            )
            .addFormDataPart(
                "fashion_image",
                fashionImageFile.name,
                fashionImageFile.asRequestBody("image/jpeg".toMediaType()),
            )
            .addFormDataPart(
                "blend_alpha",
                blendAlpha.toString(),
            )
            .build()

        val request = Request.Builder()
            .url("$baseUrl/tryon")
            .post(requestBody)
            .build()

        return httpClient.newCall(request).execute().use { response ->
            response.requireSuccess("tryon")
        }
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    private fun Response.requireSuccess(endpoint: String): ByteArray {
        if (!isSuccessful) {
            val body = body?.string() ?: ""
            throw ApiException(code, "/$endpoint returned HTTP $code: $body")
        }
        return body?.bytes() ?: throw ApiException(code, "Empty response body from /$endpoint")
    }
}

/**
 * Thrown when the backend returns a non-2xx status or an unexpected error occurs.
 */
class ApiException(val httpCode: Int, message: String) : Exception(message)
